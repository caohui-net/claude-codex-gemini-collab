#!/usr/bin/env python3
"""Tests for rmux_utils tmux detection and caching."""

import time
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from rmux_utils import check_rmux_available, get_tmux_info, _tmux_cache


def test_check_rmux_available_returns_bool():
    """Test backward compatibility: returns bool."""
    result = check_rmux_available()
    assert isinstance(result, bool)


def test_get_tmux_info_structure():
    """Test structured return has required fields."""
    info = get_tmux_info()
    assert 'available' in info
    assert 'reason' in info
    assert 'version' in info
    assert isinstance(info['available'], bool)
    assert isinstance(info['reason'], str)


def test_cache_hit_performance():
    """Test cache provides significant speedup."""
    # Clear cache
    _tmux_cache['available'] = None
    _tmux_cache['timestamp'] = 0

    # First call (cache miss)
    start1 = time.time()
    result1 = check_rmux_available()
    elapsed1 = time.time() - start1

    # Second call (cache hit)
    start2 = time.time()
    result2 = check_rmux_available()
    elapsed2 = time.time() - start2

    # Same result
    assert result1 == result2

    # Cache hit should be much faster (at least 10x)
    if elapsed1 > 0.001:  # Only compare if first call took measurable time
        assert elapsed2 < elapsed1 / 10, f"Cache not working: {elapsed1}s vs {elapsed2}s"


def test_cache_expiry():
    """Test cache expires after TTL."""
    # Clear cache
    _tmux_cache['available'] = None
    _tmux_cache['timestamp'] = 0

    # First call
    result1 = check_rmux_available()
    first_timestamp = _tmux_cache['timestamp']

    # Simulate cache expiry by setting timestamp to 70 seconds ago
    old_timestamp = time.time() - 70  # 70 seconds ago (TTL is 60s)
    _tmux_cache['timestamp'] = old_timestamp

    # Second call should refresh cache
    result2 = check_rmux_available()
    second_timestamp = _tmux_cache['timestamp']

    # Cache should have been refreshed (new timestamp should be greater than old)
    assert second_timestamp > old_timestamp + 60, \
        f"Cache should have refreshed: old={old_timestamp}, new={second_timestamp}"


def test_reason_classification():
    """Test that reason is one of expected values."""
    info = get_tmux_info()
    valid_reasons = [
        'functional',
        'not_found',
        'create_session_failed',
        'timeout',
        'command_exists_but_version_failed'
    ]

    # Reason should be valid or start with 'error:'
    assert info['reason'] in valid_reasons or info['reason'].startswith('error:'), \
        f"Unexpected reason: {info['reason']}"


def test_version_format():
    """Test version string format when available."""
    info = get_tmux_info()
    if info['available'] and info['version']:
        # Version should be non-empty string
        assert len(info['version']) > 0
        assert isinstance(info['version'], str)


def test_consistency_between_functions():
    """Test check_rmux_available() and get_tmux_info() return consistent results."""
    bool_result = check_rmux_available()
    info_result = get_tmux_info()

    assert bool_result == info_result['available'], \
        "check_rmux_available() and get_tmux_info()['available'] should match"


if __name__ == "__main__":
    # Run tests manually
    test_check_rmux_available_returns_bool()
    print("✓ test_check_rmux_available_returns_bool")

    test_get_tmux_info_structure()
    print("✓ test_get_tmux_info_structure")

    test_cache_hit_performance()
    print("✓ test_cache_hit_performance")

    test_cache_expiry()
    print("✓ test_cache_expiry")

    test_reason_classification()
    print("✓ test_reason_classification")

    test_version_format()
    print("✓ test_version_format")

    test_consistency_between_functions()
    print("✓ test_consistency_between_functions")

    print("\nAll tests passed!")
