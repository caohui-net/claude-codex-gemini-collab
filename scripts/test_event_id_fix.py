#!/usr/bin/env python3
"""Test event ID allocation with corrupted logs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_max_with_none_values():
    """Test that ID allocation handles None values correctly."""
    # Simulate corrupted events with None IDs
    events = [
        {'id': 1, 'type': 'task_created'},
        {'id': None, 'type': 'task_created'},  # Corrupted
        {'id': 3, 'type': 'completed'},
        {'id': None, 'type': 'claimed'},  # Corrupted
    ]

    # Original logic (would fail)
    try:
        next_id_old = max((e.get('id', 0) for e in events), default=0) + 1
        print(f"❌ Old logic should have failed but got: {next_id_old}")
        return False
    except TypeError:
        print("✓ Old logic fails as expected")

    # Fixed logic (should work)
    try:
        next_id_new = max((e.get('id', 0) for e in events if e.get('id') is not None), default=0) + 1
        assert next_id_new == 4, f"Expected 4, got {next_id_new}"
        print(f"✓ Fixed logic works: next_id={next_id_new}")
        return True
    except Exception as e:
        print(f"❌ Fixed logic failed: {e}")
        return False


def test_empty_events():
    """Test ID allocation with empty events list."""
    events = []

    next_id = max((e.get('id', 0) for e in events if e.get('id') is not None), default=0) + 1
    assert next_id == 1, f"Expected 1, got {next_id}"
    print(f"✓ Empty events: next_id={next_id}")
    return True


def test_all_none_events():
    """Test ID allocation when all events have None IDs."""
    events = [
        {'id': None, 'type': 'task_created'},
        {'id': None, 'type': 'claimed'},
    ]

    next_id = max((e.get('id', 0) for e in events if e.get('id') is not None), default=0) + 1
    assert next_id == 1, f"Expected 1, got {next_id}"
    print(f"✓ All-None events: next_id={next_id}")
    return True


if __name__ == "__main__":
    print("=== Event ID Fix Tests ===\n")

    tests = [
        test_max_with_none_values,
        test_empty_events,
        test_all_none_events,
    ]

    passed = sum(1 for test in tests if test())

    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
