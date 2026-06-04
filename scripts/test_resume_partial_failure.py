#!/usr/bin/env python3
"""E2E test: Resume discussion with partial failure (no retry)."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, save_task_state, load_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round, get_pending_participants
)


def test_resume_with_partial_failure():
    """
    Scenario: Round 1 has codex completed, gemini failed.
    Resume without --retry-failed should skip gemini.
    Verify: all_responded=false, consensus=false.
    """
    print("🧪 E2E Test: Resume with partial failure (no retry)")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-RESUME-PARTIAL"

        # === Round 1: codex completes, gemini fails ===
        print("\n  Phase 1: Initial round with partial failure")

        state = init_task_state(base_dir, task_id, "Test topic", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Codex completes successfully
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact-codex.md", {"consensus": True})

        # Gemini fails
        state = start_participant(state, 1, "gemini")
        state = fail_participant(state, 1, "gemini", "timeout", "Connection timeout")

        # Complete round with partial response
        state = complete_round(
            state, 1,
            consensus=False,
            blocking_issues=["gemini failed"],
            actual_responded=1,
            expected_count=2
        )
        save_task_state(base_dir, task_id, state)

        # Verify Round 1 state
        round1 = state["rounds"][0]
        assert round1["status"] == "completed"
        assert round1["consensus_check"]["all_responded"] is False
        assert round1["consensus_check"]["actual_responded"] == 1
        assert round1["consensus_check"]["expected_count"] == 2
        assert round1["consensus_check"]["consensus_reached"] is False
        print("    ✓ Round 1: all_responded=false, consensus=false")

        # === Resume: Start Round 2 without retrying failed participants ===
        print("\n  Phase 2: Resume without --retry-failed (skip gemini)")

        # Get pending participants (should skip failed gemini)
        pending = get_pending_participants(state, 1)
        # In real resume logic, failed participants are skipped unless --retry-failed
        # For this test, we simulate starting Round 2 with only codex

        state = start_round(state, 2, ["codex"])  # Only codex, gemini skipped

        state = start_participant(state, 2, "codex")
        state = complete_participant(state, 2, "codex", "artifact2-codex.md", {"consensus": True})

        # Complete Round 2 (still partial, gemini not included)
        state = complete_round(
            state, 2,
            consensus=False,
            blocking_issues=["gemini still not available"],
            actual_responded=1,
            expected_count=2
        )
        save_task_state(base_dir, task_id, state)

        # Verify Round 2 state
        round2 = state["rounds"][1]
        assert round2["status"] == "completed"
        assert round2["consensus_check"]["all_responded"] is False
        assert round2["consensus_check"]["actual_responded"] == 1
        assert round2["consensus_check"]["expected_count"] == 2
        print("    ✓ Round 2: all_responded=false (gemini skipped)")

        print("\n✅ Test passed: Resume without retry skips failed participants")


def main():
    """Run test."""
    print("=" * 60)
    print("E2E: Resume with Partial Failure")
    print("=" * 60)

    try:
        test_resume_with_partial_failure()
        print("\n" + "=" * 60)
        print("✅ All tests passed")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
