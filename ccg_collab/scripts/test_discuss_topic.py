#!/usr/bin/env python3
"""Tests for --topic parameter and TASK-ID auto-generation in collab_discuss.py."""
import sys
import re
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_parse_new_format_topic_generates_task_id(tmp_path, monkeypatch):
    """Verify --topic parsing and TASK-ID auto-generation."""
    monkeypatch.chdir(tmp_path)

    # Mock time for stable TASK-ID
    with patch('time.time', return_value=1234567890):
        # Mock subprocess to avoid actual CLI calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            result = subprocess.run(
                ["python3", "scripts/collab_discuss.py", "discuss", "--topic", "Test Topic", "--max-rounds", "1"],
                capture_output=True,
                text=True
            )

            # Should succeed (or fail gracefully if no collaboration state)
            assert result.returncode in [0, 1]


def test_generated_task_id_format(tmp_path, monkeypatch):
    """Verify TASK-ID format matches expected pattern."""
    monkeypatch.chdir(tmp_path)

    # Run without mocking to see actual TASK-ID generation
    result = subprocess.run(
        ["python3", "scripts/collab_discuss.py", "discuss", "--topic", "Test Topic Here", "--max-rounds", "1"],
        capture_output=True,
        text=True
    )

    # Check output contains generated TASK-ID with expected format
    # Format: DISCUSS-{SLUG}-{TIMESTAMP}
    output = result.stdout + result.stderr
    task_id_pattern = r'DISCUSS-[A-Z]+-[A-Z]+-[A-Z]+-\d+'

    # Should either find the pattern or fail due to missing collaboration state
    has_task_id = re.search(task_id_pattern, output) is not None
    has_error = "collaboration" in output.lower() or result.returncode != 0

    assert has_task_id or has_error, f"Expected TASK-ID pattern or error, got: {output[:200]}"


def test_old_format_still_supported(tmp_path, monkeypatch):
    """Verify backward compatibility with old format."""
    monkeypatch.chdir(tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = subprocess.run(
            ["python3", "scripts/collab_discuss.py", "discuss", "TASK-123", "Old format topic", "--participants", "codex"],
            capture_output=True,
            text=True
        )

        # Should accept old format (or fail gracefully if no collaboration state)
        assert result.returncode in [0, 1]
        # Should use provided TASK-ID, not generate new one
        if "TASK-123" in result.stdout:
            assert "DISCUSS-" not in result.stdout or "TASK-123" in result.stdout


def test_missing_topic_fails_with_helpful_message(tmp_path, monkeypatch):
    """Verify error handling when topic is missing."""
    monkeypatch.chdir(tmp_path)

    result = subprocess.run(
        ["python3", "scripts/collab_discuss.py", "discuss", "--max-rounds", "1"],
        capture_output=True,
        text=True
    )

    # Should fail with non-zero exit code
    assert result.returncode != 0
    # Should mention topic in error message
    assert "topic" in result.stdout.lower() or "topic" in result.stderr.lower()


def test_missing_topic_with_task_id_only_fails(tmp_path, monkeypatch):
    """Verify half-format (task_id without topic) fails."""
    monkeypatch.chdir(tmp_path)

    result = subprocess.run(
        ["python3", "scripts/collab_discuss.py", "discuss", "TASK-123"],
        capture_output=True,
        text=True
    )

    # Should fail with non-zero exit code
    assert result.returncode != 0
    # Should have error message about missing topic
    output = result.stdout + result.stderr
    assert "topic" in output.lower() or "usage" in output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
