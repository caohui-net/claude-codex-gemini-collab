#!/usr/bin/env python3
"""Installation verification tests."""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path for development testing
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_package_importable():
    """Test package can be imported."""
    try:
        import ccg_collab
        import ccg_collab.core.paths
        import ccg_collab.core.state
        import ccg_collab.event.io
        import ccg_collab.discuss.utils
        import ccg_collab.discuss.artifacts
        import ccg_collab.cli
        import ccg_collab.cli.discuss
        import ccg_collab.cli.event
        print("✓ All modules importable")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_cli_entry_points():
    """Test CLI entry points are callable."""
    from ccg_collab.cli import main as ccg_main
    from ccg_collab.cli.discuss import main as discuss_main
    from ccg_collab.cli.event import main as event_main

    assert callable(ccg_main)
    assert callable(discuss_main)
    assert callable(event_main)
    print("✓ CLI entry points callable")
    return True


def test_core_functions():
    """Test core functions work."""
    from ccg_collab.core.state import STATUS_MAP
    from ccg_collab.discuss.utils import compress_history, format_history_text

    assert len(STATUS_MAP) > 0
    assert callable(compress_history)
    assert callable(format_history_text)
    print("✓ Core functions work")
    return True


if __name__ == "__main__":
    print("=== Installation Verification Tests ===\n")

    tests = [
        test_package_importable,
        test_cli_entry_points,
        test_core_functions,
    ]

    failed = 0
    for test in tests:
        try:
            if not test():
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(0 if failed == 0 else 1)
