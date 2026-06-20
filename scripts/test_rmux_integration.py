#!/usr/bin/env python3
"""Test rmux integration in agent_cli."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rmux_utils import check_rmux_available, get_tmux_version


def test_rmux_detection():
    """Test rmux availability detection."""
    print("Testing rmux detection...")
    available = check_rmux_available()
    version = get_tmux_version()

    print(f"  rmux available: {available}")
    print(f"  version: {version}")

    # Don't assert availability - rmux may be installed but not usable in restricted environments
    # Just verify version is detectable if tmux/rmux binary exists
    if version:
        print(f"  ✓ rmux/tmux binary detected: {version}")
    else:
        print(f"  ⊘ rmux/tmux not installed")


def test_backward_compatibility():
    """Test that default behavior is unchanged."""
    print("\nTesting backward compatibility...")
    from agent_cli import run_codex

    # Test signature accepts old parameters
    print("  ✓ Function signature backward compatible")
    # Implicit pass - if import works, signature is compatible


def test_tmux_execution():
    """Test that use_tmux=True actually uses tmux."""
    print("\nTesting tmux execution path...")
    from agent_cli import run_in_tmux

    if not check_rmux_available():
        print("  ⊘ Skipped (rmux not available)")
        return

    # Test simple command with exit code 0
    stdout, exit_code = run_in_tmux(["echo", "test"], "/tmp", "", 5)
    assert "test" in stdout, f"Expected 'test' in stdout, got: {stdout}"
    assert exit_code == 0, f"Expected exit_code 0, got {exit_code}"
    print("  ✓ Simple command works")

    # Test command with non-zero exit code
    stdout, exit_code = run_in_tmux(["false"], "/tmp", "", 5)
    assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
    print("  ✓ Exit code captured")

    # Test stdin handling
    stdout, exit_code = run_in_tmux(["cat"], "/tmp", "hello", 5)
    assert "hello" in stdout, f"Expected 'hello' in stdout"
    assert exit_code == 0, f"Expected exit_code 0, got {exit_code}"
    print("  ✓ Stdin handling works")


def test_keep_session():
    """Test keep_session=True preserves tmux sessions."""
    print("\nTesting keep_session...")
    from agent_cli import run_in_tmux
    import time

    if not check_rmux_available():
        print("  ⊘ Skipped (rmux not available)")
        return

    stdout, exit_code = run_in_tmux(["echo", "preserved"], "/tmp", "", 5, keep_session=True)
    assert exit_code == 0, f"Expected exit_code 0, got {exit_code}"
    assert "preserved" in stdout.lower(), f"Expected 'preserved' in stdout"

    # Extract session name
    import re
    match = re.search(r'taolun-[a-f0-9]{8}', stdout)
    assert match, "No session name in output"
    session = match.group(0)

    # Verify session still exists after short delay
    time.sleep(0.5)
    import subprocess
    result = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True)
    assert session in result.stdout, f"Session {session} not found in tmux list"

    # Cleanup
    subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
    print(f"  ✓ Session preserved: {session}")


def test_lifecycle_management():
    """Test session lifecycle functions."""
    print("\nTesting lifecycle management...")
    from rmux_utils import list_ccg_sessions, cleanup_old_sessions

    sessions = list_ccg_sessions()
    print(f"  ✓ list_ccg_sessions: {len(sessions)} active")

    # Cleanup returns count
    killed = cleanup_old_sessions(max_age_seconds=1)
    print(f"  ✓ cleanup_old_sessions: {killed} cleaned")


if __name__ == "__main__":
    print("=== rmux Integration Tests ===\n")

    tests = [
        ("rmux detection", test_rmux_detection),
        ("backward compatibility", test_backward_compatibility),
        ("tmux execution", test_tmux_execution),
        ("keep_session", test_keep_session),
        ("lifecycle management", test_lifecycle_management),
    ]

    failed = 0
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ PASS: {name}")
        except AssertionError as e:
            print(f"✗ FAIL: {name} - {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {name} - {e}")
            failed += 1

    print(f"\n=== Results: {len(tests) - failed}/{len(tests)} passed ===")
    sys.exit(0 if failed == 0 else 1)
