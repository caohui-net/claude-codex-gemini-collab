#!/usr/bin/env python3
"""Tests for discussion orchestration."""

import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import compress_history, judge_consensus, build_discussion_prompt
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
