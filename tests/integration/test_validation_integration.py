"""Integration tests for agent response validation in collab_discuss workflow."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src.agent_response_validator import AgentResponseValidator
from src.collab_discuss import parse_agent_response


@pytest.fixture
def validator():
    """Create validator instance."""
    return AgentResponseValidator()


@pytest.fixture
def mock_agent_call():
    """Mock agent API call."""
    with patch('src.collab_discuss.call_agent') as mock:
        yield mock


def test_valid_response_end_to_end(validator, mock_agent_call):
    """Test valid response flows through validation."""
    mock_agent_call.return_value = {
        "agent": "codex",
        "consensus": True,
        "response": "Agreed",
        "blocking_issues": []
    }

    response = mock_agent_call()
    result = validator.validate(response)

    assert result.is_valid
    assert result.data["agent"] == "codex"


def test_invalid_response_rejected(validator, mock_agent_call):
    """Test invalid response is rejected."""
    mock_agent_call.return_value = {
        "agent": "codex"
        # Missing required fields
    }

    response = mock_agent_call()
    result = validator.validate(response)

    assert not result.is_valid
    assert "consensus" in str(result.errors)


def test_parse_agent_response_with_validation():
    """Test parse_agent_response validates before parsing."""
    raw = '{"agent": "codex", "consensus": true, "response": "OK", "blocking_issues": []}'

    parsed = parse_agent_response(raw)

    assert parsed["agent"] == "codex"
    assert parsed["consensus"] is True


def test_parse_agent_response_rejects_invalid():
    """Test parse_agent_response rejects invalid schemas."""
    raw = '{"agent": "codex"}'  # Missing required fields

    with pytest.raises(ValueError, match="validation failed"):
        parse_agent_response(raw)
