#!/usr/bin/env python3
"""Tests for discussion orchestration."""

import json
import pytest
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import compress_history, judge_consensus, build_discussion_prompt, parse_discussion_artifacts, format_history_text
from agent_cli import AgentReply


def test_compress_history_empty():
    """Test compress_history with no discussion events."""
    events = [
        {"id": 1, "type": "task_created", "task_id": "TASK-1"},
        {"id": 2, "type": "task_claimed", "task_id": "TASK-1"},
    ]
    result = compress_history(events, "TASK-1")
    assert result == ""


def test_compress_history_recent():
    """Test compress_history with recent events."""
    events = [
        {"id": 1, "type": "discussion_message", "task_id": "TASK-1", "agent": "codex", "summary": "msg1"},
        {"id": 2, "type": "discussion_message", "task_id": "TASK-1", "agent": "gemini", "summary": "msg2"},
    ]
    result = compress_history(events, "TASK-1", max_recent=2)
    assert "[codex]: msg1" in result
    assert "[gemini]: msg2" in result


def test_judge_consensus_all_agree():
    """Test consensus when all agents agree."""
    replies = [
        AgentReply("codex", "", {"consensus": True, "blocking_issues": []}, "", 1.0, 0),
        AgentReply("gemini", "", {"consensus": True, "blocking_issues": []}, "", 1.0, 0),
    ]
    consensus, blocking = judge_consensus(replies)
    assert consensus is True
    assert blocking == []


def test_judge_consensus_disagreement():
    """Test consensus when agents disagree."""
    replies = [
        AgentReply("codex", "", {"consensus": True, "blocking_issues": []}, "", 1.0, 0),
        AgentReply("gemini", "", {"consensus": False, "blocking_issues": ["issue1"]}, "", 1.0, 0),
    ]
    consensus, blocking = judge_consensus(replies)
    assert consensus is False
    assert "issue1" in blocking


def test_build_discussion_prompt():
    """Test discussion prompt generation."""
    prompt = build_discussion_prompt(
        topic="Test topic",
        task_id="TASK-1",
        agent="codex",
        round_num=1,
        history="",
        artifacts=[]
    )
    assert "TASK-1" in prompt
    assert "Test topic" in prompt
    assert "codex" in prompt
    assert "Round 1" in prompt
    assert "consensus" in prompt


def test_parse_discussion_artifacts():
    """Test parsing discussion artifacts from filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        artifacts_dir = base / ".omc" / "collaboration" / "artifacts"
        artifacts_dir.mkdir(parents=True)

        # Create test artifacts
        artifact1 = artifacts_dir / "TASK-1-discuss-r1-codex-20260601-120000.md"
        artifact1.write_text(json.dumps({
            "consensus": True,
            "decision": "Test decision",
            "reasoning": "Test reasoning",
            "blocking_issues": []
        }))

        artifact2 = artifacts_dir / "TASK-1-discuss-r2-gemini-20260601-120100.md"
        artifact2.write_text(json.dumps({
            "consensus": False,
            "decision": "Different decision",
            "reasoning": "Different reasoning",
            "blocking_issues": ["issue1"]
        }))

        # Parse artifacts
        history = parse_discussion_artifacts(base, "TASK-1")

        assert len(history) == 2
        assert history[0]["round"] == 1
        assert history[0]["agent"] == "codex"
        assert history[0]["consensus"] is True
        assert history[1]["round"] == 2
        assert history[1]["agent"] == "gemini"
        assert history[1]["consensus"] is False


def test_format_history_text():
    """Test text formatting of discussion history."""
    history = [
        {
            "round": 1,
            "agent": "codex",
            "consensus": True,
            "decision": "Test decision",
            "reasoning": "Test reasoning",
            "blocking_issues": []
        }
    ]

    text = format_history_text(history, summary=False)
    assert "[Round 1]" in text
    assert "Codex" in text
    assert "✓" in text
    assert "Test decision" in text
    assert "Test reasoning" in text


def test_format_history_text_summary():
    """Test summary formatting of discussion history."""
    history = [
        {
            "round": 1,
            "agent": "gemini",
            "consensus": False,
            "decision": "A" * 100,
            "reasoning": "Test",
            "blocking_issues": []
        }
    ]

    text = format_history_text(history, summary=True)
    assert "[Round 1]" in text
    assert "Gemini" in text
    assert "✗" in text
    assert len(text) < 200  # Summary should be truncated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
