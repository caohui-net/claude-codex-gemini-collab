#!/usr/bin/env python3
"""Tests for partial-response and recovery scenarios."""

import json
import pytest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_state import (
    init_task_state, start_round, start_participant,
    complete_participant, fail_participant, complete_round
)


def test_partial_response_observability():
    """Verify consensus_check includes actual_responded/expected_count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Init task with 3 participants
        participants = ["codex", "gemini", "claude-test"]
        task_state = init_task_state(base, "TASK-1", "Test topic", participants)

        # Start round 1
        task_state = start_round(task_state, 1, participants)

        # Only 2 of 3 participants complete
        task_state = start_participant(task_state, 1, "codex")
        task_state = complete_participant(task_state, 1, "codex", "artifact1.md", {"consensus": True})

        task_state = start_participant(task_state, 1, "gemini")
        task_state = complete_participant(task_state, 1, "gemini", "artifact2.md", {"consensus": True})

        task_state = start_participant(task_state, 1, "claude-test")
        task_state = fail_participant(task_state, 1, "claude-test", "timeout", "timed out")

        # Complete round with partial response
        task_state = complete_round(
            task_state, 1,
            consensus=False,
            blocking_issues=["Partial response"],
            actual_responded=2,
            expected_count=3
        )

        # Verify observability
        round_check = task_state["rounds"][0]["consensus_check"]
        assert round_check["all_responded"] is False
        assert round_check["actual_responded"] == 2
        assert round_check["expected_count"] == 3
        assert round_check["consensus_reached"] is False


def test_full_response_observability():
    """Verify consensus_check shows full response correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        participants = ["codex", "gemini"]
        task_state = init_task_state(base, "TASK-2", "Test topic", participants)
        task_state = start_round(task_state, 1, participants)

        # Both participants complete
        task_state = start_participant(task_state, 1, "codex")
        task_state = complete_participant(task_state, 1, "codex", "artifact1.md", {"consensus": True})

        task_state = start_participant(task_state, 1, "gemini")
        task_state = complete_participant(task_state, 1, "gemini", "artifact2.md", {"consensus": True})

        # Complete round with full response
        task_state = complete_round(
            task_state, 1,
            consensus=True,
            blocking_issues=[],
            actual_responded=2,
            expected_count=2
        )

        # Verify observability
        round_check = task_state["rounds"][0]["consensus_check"]
        assert round_check["all_responded"] is True
        assert round_check["actual_responded"] == 2
        assert round_check["expected_count"] == 2
        assert round_check["consensus_reached"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
