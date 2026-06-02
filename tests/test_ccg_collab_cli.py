#!/usr/bin/env python3
"""Tests for ccg_collab CLI wrappers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.cli.discuss import main as discuss_main
from ccg_collab.cli.event import main as event_main


def test_discuss_wrapper_callable():
    """Test discuss wrapper is callable."""
    assert callable(discuss_main)
    print("✓ discuss_main is callable")


def test_event_wrapper_callable():
    """Test event wrapper is callable."""
    assert callable(event_main)
    print("✓ event_main is callable")


def test_script_paths_exist():
    """Test that wrapped scripts exist."""
    base = Path(__file__).parent.parent
    discuss_script = base / "scripts" / "collab_discuss.py"
    event_script = base / "scripts" / "collab_event.py"

    assert discuss_script.exists(), f"Missing {discuss_script}"
    assert event_script.exists(), f"Missing {event_script}"
    print("✓ Wrapped scripts exist")


if __name__ == "__main__":
    print("=== ccg_collab.cli Tests ===\n")

    failed = 0
    tests = [test_discuss_wrapper_callable, test_event_wrapper_callable, test_script_paths_exist]

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(0 if failed == 0 else 1)
