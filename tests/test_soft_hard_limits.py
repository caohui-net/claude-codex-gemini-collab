#!/usr/bin/env python3
"""Tests for soft/hard max_rounds limits."""

import json
import pytest
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import run_discussion
from agent_cli import AgentReply


def mock_no_consensus_reply(agent):
    """Mock agent reply with consensus=false."""
    return AgentReply(
        agent=agent,
        exit_code=0,
        raw_text="[RESPONSE_START]\n{\"consensus\": false, \"decision\": \"Need more discussion\", \"blocking_issues\": [\"Issue A\"], \"reasoning\": \"Not ready\"}\n[RESPONSE_END]",
        parsed={"consensus": False, "decision": "Need more discussion", "blocking_issues": ["Issue A"], "reasoning": "Not ready"},
        artifact_path="",
        elapsed_sec=1.0
    )


@patch('collab_discuss.run_codex')
@patch('collab_discuss.run_gemini')
def test_soft_limit_reached_without_consensus(mock_gemini, mock_codex):
    """Test soft limit: max_rounds=2, no consensus, should return 0 and allow resume."""
    mock_codex.return_value = mock_no_consensus_reply("codex")
    mock_gemini.return_value = mock_no_consensus_reply("gemini")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / ".omc" / "collaboration").mkdir(parents=True)

        # Initialize required files
        (base / ".omc" / "collaboration" / "events.jsonl").write_text("")
        (base / ".omc" / "collaboration" / "state.json").write_text(
            json.dumps({"status": "idle", "last_event_id": 0})
        )

        exit_code = run_discussion(
            base, "TASK-SOFT", "Test soft limit", ["codex", "gemini"],
            max_rounds=2, hard_max_rounds=10, timeout_sec=60
        )

        # Verify: soft limit reached, return 0 (not terminal)
        assert exit_code == 0, "Soft limit should return 0"


@patch('collab_discuss.run_codex')
@patch('collab_discuss.run_gemini')
def test_hard_limit_reached(mock_gemini, mock_codex):
    """Test hard limit: reached hard_max_rounds, should force stop with return 1."""
    mock_codex.return_value = mock_no_consensus_reply("codex")
    mock_gemini.return_value = mock_no_consensus_reply("gemini")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / ".omc" / "collaboration").mkdir(parents=True)

        (base / ".omc" / "collaboration" / "events.jsonl").write_text("")
        (base / ".omc" / "collaboration" / "state.json").write_text(
            json.dumps({"status": "idle", "last_event_id": 0})
        )

        # Set max_rounds=hard_max_rounds to trigger hard limit
        exit_code = run_discussion(
            base, "TASK-HARD", "Test hard limit", ["codex", "gemini"],
            max_rounds=3, hard_max_rounds=3, timeout_sec=60
        )

        # Verify: hard limit reached, return 1 (terminal)
        assert exit_code == 1, "Hard limit should return 1"
