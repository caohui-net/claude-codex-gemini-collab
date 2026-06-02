#!/usr/bin/env python3
"""Utilities for rmux/tmux integration."""

import subprocess
from typing import Optional


def check_rmux_available() -> bool:
    """Check if rmux/tmux is available and functional.

    Returns:
        bool: True if rmux/tmux command exists and can create sessions
    """
    import uuid

    try:
        # Functional test: create and destroy a test session
        test_session = f"rmux-test-{uuid.uuid4().hex[:8]}"

        # Try to create a session
        create_result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", test_session, "true"],
            capture_output=True,
            timeout=2
        )

        if create_result.returncode != 0:
            return False

        # Cleanup test session
        subprocess.run(
            ["tmux", "kill-session", "-t", test_session],
            capture_output=True,
            timeout=2
        )

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def get_tmux_version() -> Optional[str]:
    """Get tmux/rmux version string.

    Returns:
        Optional[str]: Version string or None if unavailable
    """
    try:
        result = subprocess.run(
            ["tmux", "-V"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None
