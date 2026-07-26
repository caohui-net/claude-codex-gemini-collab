"""Unit tests for agent_cli.py utility functions.

Tests for:
- extract_response_content: Response marker extraction
- AgentConfig: Configuration management
- _http_post_json: HTTP request utility
- _load_json_config: JSON config loading
"""

import pytest
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import sys

# Import functions to test
sys.path.insert(0, str(Path(__file__).parent))
from agent_cli import (
    extract_response_content,
    AgentConfig,
    _http_post_json,
    _load_json_config,
)


class TestExtractResponseContent:
    """Test response marker extraction function."""

    def test_with_markers_basic(self):
        """Extract content between markers."""
        text = "prefix[RESPONSE_START]content[RESPONSE_END]suffix"
        result = extract_response_content(text)
        assert result == "content"

    def test_without_markers(self):
        """Return original text when no markers."""
        text = "no markers here"
        result = extract_response_content(text)
        assert result == "no markers here"

    def test_with_whitespace(self):
        """Strip whitespace around extracted content."""
        text = "[RESPONSE_START]  content  [RESPONSE_END]"
        result = extract_response_content(text)
        assert result == "content"

    def test_multiple_markers_first_pair(self):
        """Handle multiple marker pairs - extracts first."""
        text = "[RESPONSE_START]first[RESPONSE_END]middle[RESPONSE_START]second[RESPONSE_END]"
        result = extract_response_content(text)
        assert result == "first"

    def test_empty_content(self):
        """Handle empty content between markers."""
        text = "[RESPONSE_START][RESPONSE_END]"
        result = extract_response_content(text)
        assert result == ""

    def test_partial_markers(self):
        """Return original when only one marker present."""
        text1 = "[RESPONSE_START]content"
        assert extract_response_content(text1) == text1

        text2 = "content[RESPONSE_END]"
        assert extract_response_content(text2) == text2


class TestLoadJsonConfig:
    """Test JSON config loading utility with security validation."""

    def test_valid_json_file(self):
        """Load valid JSON configuration from home directory."""
        # 使用home目录以通过安全检查
        test_dir = Path.home() / ".test_agent_cli"
        test_dir.mkdir(exist_ok=True)
        path = test_dir / f"config_{uuid.uuid4()}.json"

        try:
            path.write_text(json.dumps({"key": "value", "number": 42}))
            config, error = _load_json_config(path)
            assert error == ""
            assert config == {"key": "value", "number": 42}
        finally:
            path.unlink(missing_ok=True)
            test_dir.rmdir()

    def test_path_traversal_blocked(self):
        """Block path traversal attacks outside home directory."""
        path = Path("/etc/passwd")
        config, error = _load_json_config(path)
        assert config == {}
        assert "Security" in error
        assert "outside user home" in error

    def test_missing_file(self):
        """Handle missing file in home directory gracefully."""
        path = Path.home() / "nonexistent_test_config.json"
        config, error = _load_json_config(path)
        assert config == {}
        assert "Failed to load" in error


class TestHttpPostJson:
    """Test HTTP POST JSON utility with SSRF protection."""

    @patch('urllib.request.urlopen')
    def test_successful_request(self, mock_urlopen):
        """Handle successful HTTP request with whitelisted domain."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "success"}'
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        data, status, error = _http_post_json(
            "https://api.openai.com/v1/chat",
            {"test": "data"},
            {"Content-Type": "application/json"}
        )

        assert data == {"result": "success"}
        assert status == 200
        assert error == ""

    def test_ssrf_blocked(self):
        """Block SSRF attempts to non-whitelisted domains."""
        data, status, error = _http_post_json(
            "https://malicious.com/api",
            {"test": "data"},
            {"Content-Type": "application/json"}
        )

        assert data == {}
        assert status == 0
        assert "Security" in error
        assert "not in whitelist" in error

    @patch('urllib.request.urlopen')
    def test_http_error(self, mock_urlopen):
        """Handle HTTP error responses gracefully."""
        from urllib.error import HTTPError

        mock_error = HTTPError(
            "https://api.openai.com",
            404,
            "Not Found",
            {},
            None
        )
        mock_urlopen.side_effect = mock_error

        data, status, error = _http_post_json(
            "https://api.openai.com/v1/chat",
            {"test": "data"},
            {"Content-Type": "application/json"}
        )

        assert data == {}
        assert status == 404
        assert "HTTP 404" in error


class TestAgentConfig:
    """Test AgentConfig configuration management."""

    def test_invalid_agent_type(self):
        """Handle unknown agent type."""
        config = AgentConfig("unknown")
        valid, error = config.validate("api_key")

        # Should fail validation due to missing config
        assert valid is False

    # Note: Codex config test requires complex file mocking
    # Production code tested via integration tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
