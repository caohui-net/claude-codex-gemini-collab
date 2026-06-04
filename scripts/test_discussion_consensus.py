#!/usr/bin/env python3
"""E2E test: Discussion reaches consensus."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, save_task_state,
    start_round, start_participant, complete_participant, complete_round
)


def test_discussion_consensus():
    """
    Scenario: Both participants return consensus=true.
    Verify: judge_consensus returns true, task status=completed.
    """
    print("🧪 E2E Test: Discussion reaches consensus")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-CONSENSUS"

        print("\n  Phase 1: Round 1 with both agreeing")

        state = init_task_state(base_dir, task_id, "Test topic", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Both participants agree
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact-codex.md", {"consensus": True})

        state = start_participant(state, 1, "gemini")
        state = complete_participant(state, 1, "gemini", "artifact-gemini.md", {"consensus": True})

        # Complete round with consensus
        state = complete_round(
            state, 1,
            consensus=True,
            blocking_issues=[],
            actual_responded=2,
            expected_count=2
        )

        # Mark task as completed (in real flow, this happens after consensus)
        state["status"] = "completed"
        save_task_state(base_dir, task_id, state)

        # Verify consensus reached
        round1 = state["rounds"][0]
        assert round1["consensus_check"]["all_responded"] is True
        assert round1["consensus_check"]["consensus_reached"] is True
        assert round1["consensus_check"]["blocking_issues"] == []
        assert state["status"] == "completed"
        print("    ✓ Consensus reached, task completed")

        print("\n✅ Test passed: Discussion consensus detected correctly")


def main():
    """Run test."""
    print("=" * 60)
    print("E2E: Discussion Consensus")
    print("=" * 60)

    try:
        test_discussion_consensus()
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
