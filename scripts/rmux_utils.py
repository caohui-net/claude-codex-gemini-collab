#!/usr/bin/env python3
"""Utilities for rmux/tmux integration."""

import subprocess
import time
from typing import Optional


# Process-level cache for tmux availability check
_tmux_cache = {
    'available': None,
    'timestamp': 0,
    'ttl': 60  # Cache for 60 seconds
}


def check_rmux_available() -> bool:
    """Check if rmux/tmux is available and functional.

    Uses process-level cache with 60s TTL to avoid repeated session creation.

    Returns:
        bool: True if rmux/tmux command exists and can create sessions
    """
    import uuid

    # Check cache
    current_time = time.time()
    if (_tmux_cache['available'] is not None and
        current_time - _tmux_cache['timestamp'] < _tmux_cache['ttl']):
        return _tmux_cache['available']

    # Cache miss or expired - perform check
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
            result = False
        else:
            # Cleanup test session
            subprocess.run(
                ["tmux", "kill-session", "-t", test_session],
                capture_output=True,
                timeout=2
            )
            result = True

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        result = False

    # Update cache
    _tmux_cache['available'] = result
    _tmux_cache['timestamp'] = current_time

    return result


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


def list_ccg_sessions() -> list:
    """List all active CCG tmux sessions.

    Returns:
        List of dicts with keys: name, created, attached
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_created}:#{session_attached}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return []

        sessions = []
        for line in result.stdout.strip().split('\n'):
            if not line or not line.startswith('ccg-'):
                continue

            parts = line.split(':')
            if len(parts) >= 3:
                sessions.append({
                    'name': parts[0],
                    'created': int(parts[1]),
                    'attached': parts[2] == '1'
                })

        return sessions

    except Exception:
        return []


def cleanup_old_sessions(max_age_seconds: int = 3600) -> int:
    """Clean up old CCG sessions exceeding max age.

    Args:
        max_age_seconds: Maximum session age (default: 1 hour)

    Returns:
        Number of sessions killed
    """
    import time

    sessions = list_ccg_sessions()
    current_time = int(time.time())
    killed = 0

    for session in sessions:
        age = current_time - session['created']
        if age > max_age_seconds and not session['attached']:
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session['name']],
                    capture_output=True,
                    timeout=5
                )
                killed += 1
            except Exception:
                pass

    return killed
