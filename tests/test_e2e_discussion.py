#!/usr/bin/env python3
"""End-to-end test for discussion feature using mock agents."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import compress_history, judge_consensus, build_discussion_prompt
from agent_cli import AgentReply


def test_e2e_discussion_consensus():
    """Test full discussion flow reaching consensus."""
    print("Testing E2E discussion with consensus...")

    # Mock agent replies with consensus
    replies = [
        AgentReply(
            "codex",
            '{"consensus": true, "decision": "Use PostgreSQL", "blocking_issues": [], "reasoning": "Good choice"}',
            {"consensus": True, "decision": "Use PostgreSQL", "blocking_issues": [], "reasoning": "Good choice"},
            "",
            1.0,
            0
        ),
        AgentReply(
            "gemini",
            '{"consensus": true, "decision": "Agree on PostgreSQL", "blocking_issues": [], "reasoning": "Makes sense"}',
            {"consensus": True, "decision": "Agree on PostgreSQL", "blocking_issues": [], "reasoning": "Makes sense"},
            "",
            1.0,
            0
        ),
    ]

    consensus, blocking = judge_consensus(replies)
    assert consensus is True, "Should reach consensus when all agree"
    assert blocking == [], "Should have no blocking issues"
    print("✓ Consensus reached correctly")


def test_e2e_discussion_no_consensus():
    """Test full discussion flow without consensus."""
    print("Testing E2E discussion without consensus...")

    # Mock agent replies with disagreement
    replies = [
        AgentReply(
            "codex",
            '{"consensus": true, "decision": "Use PostgreSQL", "blocking_issues": [], "reasoning": "Good"}',
            {"consensus": True, "decision": "Use PostgreSQL", "blocking_issues": [], "reasoning": "Good"},
            "",
            1.0,
            0
        ),
        AgentReply(
            "gemini",
            '{"consensus": false, "decision": "Prefer MongoDB", "blocking_issues": ["Schema flexibility"], "reasoning": "NoSQL better"}',
            {"consensus": False, "decision": "Prefer MongoDB", "blocking_issues": ["Schema flexibility"], "reasoning": "NoSQL better"},
            "",
            1.0,
            0
        ),
    ]

    consensus, blocking = judge_consensus(replies)
    assert consensus is False, "Should not reach consensus when agents disagree"
    assert "Schema flexibility" in blocking, "Should capture blocking issues"
    print("✓ No consensus detected correctly")


def test_e2e_markdown_stripping():
    """Test markdown code block stripping."""
    print("Testing markdown stripping...")

    from agent_cli import strip_markdown_json

    # Test with markdown wrapper
    text = "```json\n{\"test\": true}\n```"
    stripped = strip_markdown_json(text)
    assert stripped == '{"test": true}', f"Should strip markdown, got: {stripped}"
    print("✓ Markdown stripping works")


def test_e2e_history_compression():
    """Test history compression."""
    print("Testing history compression...")

    events = [
        {"id": 1, "type": "discussion_message", "task_id": "TASK-1", "agent": "codex", "summary": "First message"},
        {"id": 2, "type": "discussion_message", "task_id": "TASK-1", "agent": "gemini", "summary": "Second message"},
        {"id": 3, "type": "discussion_message", "task_id": "TASK-1", "agent": "codex", "summary": "Third message"},
    ]

    history = compress_history(events, "TASK-1", max_recent=2)
    assert "[codex]: Third message" in history, "Should include recent messages"
    assert "[gemini]: Second message" in history, "Should include recent messages"
    print("✓ History compression works")


if __name__ == "__main__":
    print("Running end-to-end tests...\n")

    try:
        test_e2e_discussion_consensus()
        test_e2e_discussion_no_consensus()
        test_e2e_markdown_stripping()
        test_e2e_history_compression()

        print("\n✅ All E2E tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
