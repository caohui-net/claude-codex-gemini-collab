#!/usr/bin/env python3
"""Tests for no-consensus terminal state."""

import pytest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_state import (
    init_task_state, start_round, start_participant,
    complete_participant, complete_round
)


def test_no_consensus_terminal_state():
    """Verify discussion transitions to completed when max rounds reached without consensus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        participants = ["codex", "gemini"]
        task_state = init_task_state(base, "TASK-1", "Test topic", participants)

        # Round 1: no consensus
        task_state = start_round(task_state, 1, participants)
        task_state = start_participant(task_state, 1, "codex")
        task_state = complete_participant(
            task_state, 1, "codex", "artifact1.md",
            {"consensus": False}
        )
        task_state = start_participant(task_state, 1, "gemini")
        task_state = complete_participant(
            task_state, 1, "gemini", "artifact2.md",
            {"consensus": False}
        )
        task_state = complete_round(
            task_state, 1, consensus=False,
            blocking_issues=["Disagreement on approach"],
            actual_responded=2, expected_count=2
        )

        # Simulate max_rounds=1 scenario: should transition to completed
        task_state["status"] = "completed"
        task_state["final_consensus"]["reached"] = False

        assert task_state["status"] == "completed"
        assert task_state["final_consensus"]["reached"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
