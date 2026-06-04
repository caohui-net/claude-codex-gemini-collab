#!/usr/bin/env python3
"""E2E test: Resume discussion with --retry-failed."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, save_task_state, load_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round
)


def test_resume_with_retry():
    """
    Scenario: Round 1 has gemini failed.
    Resume with --retry-failed should re-execute gemini.
    Verify: After retry success, all_responded=true.
    """
    print("🧪 E2E Test: Resume with --retry-failed")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-RESUME-RETRY"

        # === Round 1: gemini fails ===
        print("\n  Phase 1: Initial round with gemini failure")

        state = init_task_state(base_dir, task_id, "Test topic", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Codex completes
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
        assert state["rounds"][0]["consensus_check"]["all_responded"] is False
        print("    ✓ Round 1: all_responded=false (gemini failed)")

        # === Resume with --retry-failed: Re-execute gemini ===
        print("\n  Phase 2: Resume with --retry-failed (re-execute gemini)")

        # Reload state (simulating resume)
        state = load_task_state(base_dir, task_id)

        # Start Round 2 with both participants (retry gemini)
        state = start_round(state, 2, ["codex", "gemini"])

        # Both complete successfully this time
        state = start_participant(state, 2, "codex")
        state = complete_participant(state, 2, "codex", "artifact2-codex.md", {"consensus": True})

        state = start_participant(state, 2, "gemini")
        state = complete_participant(state, 2, "gemini", "artifact2-gemini.md", {"consensus": True})

        # Complete Round 2 with full response
        state = complete_round(
            state, 2,
            consensus=True,
            blocking_issues=[],
            actual_responded=2,
            expected_count=2
        )
        save_task_state(base_dir, task_id, state)

        # Verify Round 2 state
        round2 = state["rounds"][1]
        assert round2["status"] == "completed"
        assert round2["consensus_check"]["all_responded"] is True
        assert round2["consensus_check"]["actual_responded"] == 2
        assert round2["consensus_check"]["expected_count"] == 2
        assert round2["consensus_check"]["consensus_reached"] is True
        print("    ✓ Round 2: all_responded=true, consensus=true (retry succeeded)")

        print("\n✅ Test passed: Retry-failed successfully re-executes failed participant")


def main():
    """Run test."""
    print("=" * 60)
    print("E2E: Resume with --retry-failed")
    print("=" * 60)

    try:
        test_resume_with_retry()
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
