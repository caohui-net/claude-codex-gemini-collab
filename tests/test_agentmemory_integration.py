#!/usr/bin/env python3
"""Test agentmemory backend integration with iii-sdk."""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.coordination.agentmemory import AgentMemoryCoordination


def test_connection():
    """Test basic connection to iii-engine."""
    print("Testing connection to iii-engine...")
    try:
        coord = AgentMemoryCoordination("ws://localhost:49134")
        print("✓ Connected to iii-engine")
        return coord
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None


def test_lease_operations(coord):
    """Test lease acquire/release."""
    print("\nTesting lease operations...")
    try:
        # Acquire lease
        acquired = coord.acquire_lock("test-resource", "test-agent", 60.0)
        print(f"✓ Lease acquire: {acquired}")

        # Release lease
        released = coord.release_lock("test-resource", "test-agent")
        print(f"✓ Lease release: {released}")

        return True
    except Exception as e:
        print(f"✗ Lease operations failed: {e}")
        return False


def test_signal_operations(coord):
    """Test signal send/read."""
    print("\nTesting signal operations...")
    try:
        # Send signal
        coord.send_signal("test-signal", {"data": "hello"}, None)
        print("✓ Signal sent")

        # Read signal (with short timeout)
        result = coord.wait_signal("test-signal", 2.0)
        print(f"✓ Signal read: {result}")

        return True
    except Exception as e:
        print(f"✗ Signal operations failed: {e}")
        return False


if __name__ == "__main__":
    coord = test_connection()
    if coord:
        test_lease_operations(coord)
        test_signal_operations(coord)
        print("\n✓ All tests completed")
    else:
        print("\n✗ Tests aborted - connection failed")
        sys.exit(1)
