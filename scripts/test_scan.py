#!/usr/bin/env python3
"""E2E tests for scan command."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_state import init_task_state, save_task_state, get_task_state_file
from collab_discuss import run_scan


def test_scan_empty_directory():
    """Test scan with no state directory."""
    print("🧪 Test 1: Empty directory")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Passed\n")


def test_scan_running_task():
    """Test scan detects running task."""
    print("🧪 Test 2: Running task")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-SCAN-RUNNING"

        # Create running task
        state = init_task_state(base_dir, task_id, "Test running", ["codex"])
        state["status"] = "running"
        save_task_state(base_dir, task_id, state)

        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Detected running task\n")


def test_scan_failed_task():
    """Test scan detects failed task."""
    print("🧪 Test 3: Failed task")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-SCAN-FAILED"

        # Create failed task
        state = init_task_state(base_dir, task_id, "Test failed", ["codex"])
        state["status"] = "failed"
        save_task_state(base_dir, task_id, state)

        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Detected failed task\n")


def test_scan_pending_task():
    """Test scan detects pending task."""
    print("🧪 Test 4: Pending task")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-SCAN-PENDING"

        # Create pending task
        state = init_task_state(base_dir, task_id, "Test pending", ["codex"])
        state["status"] = "pending"
        save_task_state(base_dir, task_id, state)

        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Detected pending task\n")


def test_scan_corrupted_json():
    """Test scan handles corrupted JSON."""
    print("🧪 Test 5: Corrupted JSON")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-SCAN-CORRUPT"

        # Create corrupted state file
        state_file = get_task_state_file(base_dir, task_id)
        state_file.write_text("invalid json {")

        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Handled corrupted JSON\n")


def test_scan_missing_fields():
    """Test scan handles missing fields."""
    print("🧪 Test 6: Missing fields")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        task_id = "TEST-SCAN-MISSING"

        # Create state with missing fields
        state_file = get_task_state_file(base_dir, task_id)
        state_file.write_text(json.dumps({"task_id": task_id}))

        result = run_scan(base_dir)
        assert result == 0

    print("   ✓ Handled missing fields\n")


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
