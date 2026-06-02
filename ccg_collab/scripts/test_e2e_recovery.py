#!/usr/bin/env python3
"""End-to-end recovery test for discussion system."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, load_task_state, save_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round, get_task_state_file
)


def test_e2e_checkpoint_and_resume():
    """Test E2E: checkpoint, interrupt, status, resume."""
    base_dir = Path.cwd()
    task_id = "TEST-E2E-CHECKPOINT"

    print("🧪 E2E Test 1: Checkpoint and Resume")

    # Initialize task
    state = init_task_state(base_dir, task_id, "E2E test", ["codex", "gemini"])
    print("   ✓ Task initialized")

    # Start round 1
    state = start_round(state, 1, ["codex", "gemini"])
    save_task_state(base_dir, task_id, state)

    # Complete codex
    state = start_participant(state, 1, "codex")
    save_task_state(base_dir, task_id, state)
    state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": False})
    save_task_state(base_dir, task_id, state)
    print("   ✓ Codex completed, checkpoint saved")

    # Simulate interrupt (gemini not started)
    print("   ⚠️  Simulating interrupt...")

    # Reload state (simulate resume)
    reloaded = load_task_state(base_dir, task_id)
    assert reloaded["rounds"][0]["participants"][0]["status"] == "completed"
    assert reloaded["rounds"][0]["participants"][1]["status"] == "pending"
    print("   ✓ State reloaded, codex completed, gemini pending")

    # Resume: complete gemini
    state = reloaded
    state = start_participant(state, 1, "gemini")
    save_task_state(base_dir, task_id, state)
    state = complete_participant(state, 1, "gemini", "artifact2.md", {"consensus": True})
    save_task_state(base_dir, task_id, state)
    print("   ✓ Resumed and completed gemini")

    # Complete round
    state = complete_round(state, 1, True, [])
    save_task_state(base_dir, task_id, state)
    assert state["status"] == "completed"
    print("   ✓ Round completed, consensus reached")

    # Cleanup
    get_task_state_file(base_dir, task_id).unlink()
    print("   ✓ Cleanup done\n")


def test_e2e_failure_and_retry():
    """Test E2E: failure, status, retry."""
    base_dir = Path.cwd()
    task_id = "TEST-E2E-RETRY"

    print("🧪 E2E Test 2: Failure and Retry")

    # Initialize and start
    state = init_task_state(base_dir, task_id, "E2E retry test", ["codex", "gemini"])
    state = start_round(state, 1, ["codex", "gemini"])
    save_task_state(base_dir, task_id, state)

    # Codex completes
    state = start_participant(state, 1, "codex")
    save_task_state(base_dir, task_id, state)
    state = complete_participant(state, 1, "codex", "artifact1.md", {"consensus": False})
    save_task_state(base_dir, task_id, state)

    # Gemini fails
    state = start_participant(state, 1, "gemini")
    save_task_state(base_dir, task_id, state)
    state = fail_participant(state, 1, "gemini", "timeout", "execution exceeded 180s")
    save_task_state(base_dir, task_id, state)
    print("   ✓ Gemini failed with timeout")

    # Check status
    reloaded = load_task_state(base_dir, task_id)
    assert len(reloaded["failures"]) == 1
    assert reloaded["failures"][0]["error_type"] == "timeout"
    print("   ✓ Failure recorded in state")

    # Retry: reset gemini to pending
    state = reloaded
    state["rounds"][0]["participants"][1]["status"] = "pending"
    state["rounds"][0]["participants"][1]["error"] = None
    save_task_state(base_dir, task_id, state)
    print("   ✓ Gemini reset to pending for retry")

    # Retry: complete gemini
    state = start_participant(state, 1, "gemini")
    save_task_state(base_dir, task_id, state)
    state = complete_participant(state, 1, "gemini", "artifact2.md", {"consensus": True})
    save_task_state(base_dir, task_id, state)
    print("   ✓ Retry succeeded")

    # Complete round
    state = complete_round(state, 1, True, [])
    save_task_state(base_dir, task_id, state)
    assert state["status"] == "completed"
    print("   ✓ Round completed after retry")

    # Cleanup
    get_task_state_file(base_dir, task_id).unlink()
    print("   ✓ Cleanup done\n")


def test_e2e_corrupted_state():
    """Test E2E: corrupted state handling."""
    base_dir = Path.cwd()
    task_id = "TEST-E2E-CORRUPT"

    print("🧪 E2E Test 3: Corrupted State Handling")

    # Initialize task
    state = init_task_state(base_dir, task_id, "E2E corrupt test", ["codex"])
    state_file = get_task_state_file(base_dir, task_id)
    print("   ✓ Task initialized")

    # Corrupt state file
    state_file.write_text("invalid json {")
    print("   ✓ State file corrupted")

    # Try to load
    reloaded = load_task_state(base_dir, task_id)
    assert reloaded is None
    print("   ✓ Corrupted state returns None (graceful failure)")

    # Cleanup
    state_file.unlink()
    print("   ✓ Cleanup done\n")


def main():
    """Run all E2E tests."""
    print("=" * 60)
    print("End-to-End Recovery Tests")
    print("=" * 60 + "\n")

    try:
        test_e2e_checkpoint_and_resume()
        test_e2e_failure_and_retry()
        test_e2e_corrupted_state()

        print("=" * 60)
        print("✅ All E2E tests passed")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ E2E test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
