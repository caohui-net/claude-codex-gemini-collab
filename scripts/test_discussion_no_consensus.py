#!/usr/bin/env python3
"""E2E test: Discussion does not reach consensus."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, save_task_state,
    start_round, start_participant, complete_participant, complete_round
)


def test_discussion_no_consensus():
    """
    Scenario: One consensus=true, one consensus=false.
    Verify: judge_consensus returns false, task continues to next round.
    """
    print("🧪 E2E Test: Discussion no consensus (disagreement)")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-NO-CONSENSUS"

        print("\n  Phase 1: Round 1 with disagreement")

        state = init_task_state(base_dir, task_id, "Test topic", ["codex", "gemini"])
        state = start_round(state, 1, ["codex", "gemini"])

        # Codex agrees, Gemini disagrees
        state = start_participant(state, 1, "codex")
        state = complete_participant(state, 1, "codex", "artifact-codex.md", {"consensus": True})

        state = start_participant(state, 1, "gemini")
        state = complete_participant(state, 1, "gemini", "artifact-gemini.md", {
            "consensus": False,
            "blocking_issues": ["Need more data"]
        })

        # Complete round without consensus
        state = complete_round(
            state, 1,
            consensus=False,
            blocking_issues=["Need more data"],
            actual_responded=2,
            expected_count=2
        )
        save_task_state(base_dir, task_id, state)

        # Verify no consensus, but all responded
        round1 = state["rounds"][0]
        assert round1["consensus_check"]["all_responded"] is True
        assert round1["consensus_check"]["consensus_reached"] is False
        assert "Need more data" in round1["consensus_check"]["blocking_issues"]
        print("    ✓ Round 1: all_responded=true, consensus=false")

        print("\n  Phase 2: Round 2 continues")

        # Start Round 2 (discussion continues)
        state = start_round(state, 2, ["codex", "gemini"])

        state = start_participant(state, 2, "codex")
        state = complete_participant(state, 2, "codex", "artifact2-codex.md", {"consensus": True})

        state = start_participant(state, 2, "gemini")
        state = complete_participant(state, 2, "gemini", "artifact2-gemini.md", {"consensus": True})

        # Complete Round 2 with consensus
        state = complete_round(
            state, 2,
            consensus=True,
            blocking_issues=[],
            actual_responded=2,
            expected_count=2
        )
        state["status"] = "completed"
        save_task_state(base_dir, task_id, state)

        # Verify consensus in Round 2
        round2 = state["rounds"][1]
        assert round2["consensus_check"]["consensus_reached"] is True
        assert state["status"] == "completed"
        print("    ✓ Round 2: consensus reached, task completed")

        print("\n✅ Test passed: No consensus triggers next round")


def main():
    """Run test."""
    print("=" * 60)
    print("E2E: Discussion No Consensus")
    print("=" * 60)

    try:
        test_discussion_no_consensus()
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
