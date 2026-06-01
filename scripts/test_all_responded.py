#!/usr/bin/env python3
"""Test all_responded field semantics."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, save_task_state, start_round,
    start_participant, complete_participant, fail_participant,
    complete_round
)


def test_all_responded_all_success():
    """Scenario 1: All participants responded successfully."""
    print("🧪 Test 1: All participants responded")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-ALL-SUCCESS"

        # Create task with 2 participants
        state = init_task_state(base_dir, task_id, "Test", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Both participants complete
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": True})
        state = start_participant(state, 1, "gemini")
        state = complete_participant(state, 1, "gemini", "artifact2.md", {"consensus": True})

        # Complete round with all responded
        state = complete_round(state, 1, True, [], actual_responded=2, expected_count=2)
        save_task_state(base_dir, task_id, state)

        # Verify
        assert state["rounds"][0]["consensus_check"]["all_responded"] == True
        assert state["rounds"][0]["consensus_check"]["consensus_reached"] == True
        print("   ✓ all_responded=True, consensus=True\n")


def test_all_responded_partial_failure():
    """Scenario 2: One participant failed."""
    print("🧪 Test 2: Partial failure (one failed)")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-PARTIAL-FAIL"

        # Create task with 2 participants
        state = init_task_state(base_dir, task_id, "Test", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # One completes, one fails
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": True})
        state = start_participant(state, 1, "gemini")
        state = fail_participant(state, 1, "gemini", "timeout", "timeout error")

        # Complete round with partial response
        state = complete_round(state, 1, False, ["gemini failed"],
                             actual_responded=1, expected_count=2)
        save_task_state(base_dir, task_id, state)

        # Verify
        assert state["rounds"][0]["consensus_check"]["all_responded"] == False
        assert state["rounds"][0]["consensus_check"]["consensus_reached"] == False
        print("   ✓ all_responded=False, consensus=False\n")


def test_all_responded_no_consensus():
    """Scenario 3: All responded but no consensus."""
    print("🧪 Test 3: All responded, no consensus")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-NO-CONSENSUS"

        # Create task with 2 participants
        state = init_task_state(base_dir, task_id, "Test", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Both complete but disagree
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": True})
        state = start_participant(state, 1, "gemini")
        state = complete_participant(state, 1, "gemini", "artifact2.md", {"consensus": False})

        # Complete round with all responded but no consensus
        state = complete_round(state, 1, False, ["disagreement"],
                             actual_responded=2, expected_count=2)
        save_task_state(base_dir, task_id, state)

        # Verify
        assert state["rounds"][0]["consensus_check"]["all_responded"] == True
        assert state["rounds"][0]["consensus_check"]["consensus_reached"] == False
        print("   ✓ all_responded=True, consensus=False\n")


def test_all_responded_fallback():
    """Scenario 4: Fallback when counts not provided."""
    print("🧪 Test 4: Fallback (no counts provided)")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-FALLBACK"

        # Create task with 2 participants
        state = init_task_state(base_dir, task_id, "Test", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Both complete
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": True})
        state = start_participant(state, 1, "gemini")
        state = complete_participant(state, 1, "gemini", "artifact2.md", {"consensus": True})

        # Complete round without counts (fallback)
        state = complete_round(state, 1, True, [])
        save_task_state(base_dir, task_id, state)

        # Verify fallback checks participant statuses
        assert state["rounds"][0]["consensus_check"]["all_responded"] == True
        print("   ✓ Fallback: all_responded=True (all participants completed)\n")


def test_all_responded_fallback_with_failure():
    """Scenario 5: Fallback detects failure."""
    print("🧪 Test 5: Fallback with failure")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-FALLBACK-FAIL"

        # Create task with 2 participants
        state = init_task_state(base_dir, task_id, "Test", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # One completes, one fails
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": True})
        state = start_participant(state, 1, "gemini")
        state = fail_participant(state, 1, "gemini", "timeout", "timeout error")

        # Complete round without counts (fallback)
        state = complete_round(state, 1, False, ["gemini failed"])
        save_task_state(base_dir, task_id, state)

        # Verify fallback detects failure
        assert state["rounds"][0]["consensus_check"]["all_responded"] == False
        print("   ✓ Fallback: all_responded=False (one participant failed)\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("all_responded Field Semantics Tests")
    print("=" * 60 + "\n")

    try:
        test_all_responded_all_success()
        test_all_responded_partial_failure()
        test_all_responded_no_consensus()
        test_all_responded_fallback()
        test_all_responded_fallback_with_failure()

        print("=" * 60)
        print("✅ All all_responded tests passed")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
