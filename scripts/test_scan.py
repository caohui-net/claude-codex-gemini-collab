#!/usr/bin/env python3
"""E2E tests for scan command."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import init_task_state, save_task_state, get_task_state_file
from collab_discuss import run_scan


def test_scan_empty_directory():
    """Test scan with no state directory."""
    base_dir = Path.cwd()
    state_dir = base_dir / ".omc" / "collaboration" / "state"

    # Ensure state dir doesn't exist
    if state_dir.exists():
        for f in state_dir.glob("*.json"):
            f.unlink()
        state_dir.rmdir()

    print("🧪 Test 1: Empty directory")
    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Passed\n")


def test_scan_running_task():
    """Test scan detects running task."""
    base_dir = Path.cwd()
    task_id = "TEST-SCAN-RUNNING"

    print("🧪 Test 2: Running task")

    # Create running task
    state = init_task_state(base_dir, task_id, "Test running", ["codex"])
    state["status"] = "running"
    save_task_state(base_dir, task_id, state)

    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Detected running task\n")

    # Cleanup
    get_task_state_file(base_dir, task_id).unlink()


def test_scan_failed_task():
    """Test scan detects failed task."""
    base_dir = Path.cwd()
    task_id = "TEST-SCAN-FAILED"

    print("🧪 Test 3: Failed task")

    # Create failed task
    state = init_task_state(base_dir, task_id, "Test failed", ["codex"])
    state["status"] = "failed"
    save_task_state(base_dir, task_id, state)

    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Detected failed task\n")

    # Cleanup
    get_task_state_file(base_dir, task_id).unlink()


def test_scan_pending_task():
    """Test scan detects pending task."""
    base_dir = Path.cwd()
    task_id = "TEST-SCAN-PENDING"

    print("🧪 Test 4: Pending task")

    # Create pending task
    state = init_task_state(base_dir, task_id, "Test pending", ["codex"])
    state["status"] = "pending"
    save_task_state(base_dir, task_id, state)

    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Detected pending task\n")

    # Cleanup
    get_task_state_file(base_dir, task_id).unlink()


def test_scan_corrupted_json():
    """Test scan handles corrupted JSON."""
    base_dir = Path.cwd()
    task_id = "TEST-SCAN-CORRUPT"

    print("🧪 Test 5: Corrupted JSON")

    # Create corrupted state file
    state_file = get_task_state_file(base_dir, task_id)
    state_file.write_text("invalid json {")

    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Handled corrupted JSON\n")

    # Cleanup
    state_file.unlink()


def test_scan_missing_fields():
    """Test scan handles missing fields."""
    base_dir = Path.cwd()
    task_id = "TEST-SCAN-MISSING"

    print("🧪 Test 6: Missing fields")

    # Create state with missing fields
    state_file = get_task_state_file(base_dir, task_id)
    state_file.write_text(json.dumps({"task_id": task_id}))

    result = run_scan(base_dir)
    assert result == 0
    print("   ✓ Handled missing fields\n")

    # Cleanup
    state_file.unlink()


def main():
    """Run all scan tests."""
    print("=" * 60)
    print("Scan Command E2E Tests")
    print("=" * 60 + "\n")

    try:
        test_scan_empty_directory()
        test_scan_running_task()
        test_scan_failed_task()
        test_scan_pending_task()
        test_scan_corrupted_json()
        test_scan_missing_fields()

        print("=" * 60)
        print("✅ All scan tests passed")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
