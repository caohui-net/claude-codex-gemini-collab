#!/usr/bin/env python3
"""Simple recovery test for discussion system."""

import json
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from collab_state import (
    init_task_state, load_task_state, save_task_state,
    start_round, start_participant, complete_participant, fail_participant,
    complete_round, get_task_state_file
)


def test_basic_recovery():
    """Test basic recovery flow."""
    base_dir = Path.cwd()
    task_id = "TEST-RECOVERY"

    print("🧪 Test 1: Initialize task state")
    state = init_task_state(base_dir, task_id, "Test recovery", ["codex", "gemini"])
    assert state["status"] == "pending"
    assert state["task_id"] == task_id
    print("   ✓ Task state initialized")

    print("\n🧪 Test 2: Start round")
    state = start_round(state, 1, ["codex", "gemini"])
    save_task_state(base_dir, task_id, state)
    assert state["status"] == "running"
    assert len(state["rounds"]) == 1
    print("   ✓ Round started")

    print("\n🧪 Test 3: Complete participant")
    state = start_participant(state, 1, "codex")
    save_task_state(base_dir, task_id, state)
    state = complete_participant(state, 1, "codex", "artifact.md", {"consensus": True})
    save_task_state(base_dir, task_id, state)
    assert state["rounds"][0]["participants"][0]["status"] == "completed"
    print("   ✓ Participant completed")

    print("\n🧪 Test 4: Simulate crash and reload")
    state_file = get_task_state_file(base_dir, task_id)
    assert state_file.exists()
    reloaded_state = load_task_state(base_dir, task_id)
    assert reloaded_state is not None
    assert reloaded_state["task_id"] == task_id
    assert reloaded_state["rounds"][0]["participants"][0]["status"] == "completed"
    print("   ✓ State reloaded after crash")

    print("\n🧪 Test 5: Fail participant")
    state = start_participant(state, 1, "gemini")
    save_task_state(base_dir, task_id, state)
    state = fail_participant(state, 1, "gemini", "timeout", "execution exceeded 180s")
    save_task_state(base_dir, task_id, state)
    assert state["rounds"][0]["participants"][1]["status"] == "failed"
    assert len(state["failures"]) == 1
    print("   ✓ Participant failed")

    print("\n🧪 Test 6: Complete round")
    state = complete_round(state, 1, False, ["timeout"])
    save_task_state(base_dir, task_id, state)
    assert state["rounds"][0]["status"] == "completed"
    print("   ✓ Round completed")

    print("\n🧪 Test 7: Cleanup")
    state_file.unlink()
    print("   ✓ Test state cleaned up")

    print("\n✅ All recovery tests passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_basic_recovery())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
