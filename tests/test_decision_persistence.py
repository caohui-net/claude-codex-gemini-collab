#!/usr/bin/env python3
"""Tests for final_consensus.decision persistence."""

import json
import pytest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_state import (
    init_task_state, start_round, start_participant,
    complete_participant, complete_round, save_task_state, load_task_state
)


def test_decision_content_extracted_not_placeholder():
    """Verify decision field contains actual content, not 'Consensus reached'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        participants = ["codex", "gemini"]
        task_state = init_task_state(base, "TASK-1", "Test topic", participants)
        task_state = start_round(task_state, 1, participants)

        # Both participants complete with consensus
        task_state = start_participant(task_state, 1, "codex")
        task_state = complete_participant(
            task_state, 1, "codex", "artifact1.md",
            {"consensus": True, "decision": "Use approach A with modifications"}
        )

        task_state = start_participant(task_state, 1, "gemini")
        task_state = complete_participant(
            task_state, 1, "gemini", "artifact2.md",
            {"consensus": True, "decision": "Agree with approach A"}
        )

        # Complete round with consensus
        task_state = complete_round(
            task_state, 1, consensus=True, blocking_issues=[],
            actual_responded=2, expected_count=2
        )

        # Verify decision is NOT placeholder
        decision = task_state["final_consensus"]["decision"]
        assert decision != "Consensus reached", \
            f"Decision should contain actual content, not placeholder. Got: {decision}"
        assert len(decision) > 20, \
            f"Decision should have substantial content. Got: {decision}"


def test_decision_persists_across_save_load():
    """Verify decision survives save/load cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        participants = ["codex", "gemini"]
        task_state = init_task_state(base, "TASK-2", "Test topic", participants)
        task_state = start_round(task_state, 1, participants)

        task_state = start_participant(task_state, 1, "codex")
        task_state = complete_participant(
            task_state, 1, "codex", "artifact1.md",
            {"consensus": True, "decision": "Decision from Codex response"}
        )

        task_state = start_participant(task_state, 1, "gemini")
        task_state = complete_participant(
            task_state, 1, "gemini", "artifact2.md",
            {"consensus": True, "decision": "Decision from Gemini response"}
        )

        task_state = complete_round(
            task_state, 1, consensus=True, blocking_issues=[],
            actual_responded=2, expected_count=2
        )

        original_decision = task_state["final_consensus"]["decision"]

        # Save and reload
        save_task_state(base, "TASK-2", task_state)
        loaded_state = load_task_state(base, "TASK-2")

        # Verify decision persisted
        assert loaded_state["final_consensus"]["decision"] == original_decision
        assert loaded_state["final_consensus"]["decision"] != "Consensus reached"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
