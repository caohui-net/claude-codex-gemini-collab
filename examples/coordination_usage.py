#!/usr/bin/env python3
"""Example: Using coordination provider in collab scripts.

Demonstrates how to integrate the coordination abstraction layer
into collaboration workflows.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.coordination.config import CollabConfig


def example_lock_usage():
    """Example: Acquire/release locks for exclusive resource access."""
    config = CollabConfig()
    coord = config.get_coordination_provider()

    print("Acquiring lock on 'task-123'...")
    acquired = coord.acquire_lock("task-123", "agent-claude", 60.0)
    print(f"Lock acquired: {acquired}")

    if acquired:
        print("Working on task...")
        # Do work here

        print("Releasing lock...")
        released = coord.release_lock("task-123", "agent-claude")
        print(f"Lock released: {released}")


def example_signal_usage():
    """Example: Send/receive signals for agent communication."""
    config = CollabConfig()
    coord = config.get_coordination_provider()

    print("Sending signal...")
    coord.send_signal("task-complete", {"task_id": "123", "result": "success"}, "agent-codex")

    print("Waiting for signal...")
    result = coord.wait_signal("task-ready", 5.0)
    print(f"Received signal: {result}")


def example_action_usage():
    """Example: Enqueue/claim actions for distributed task management."""
    config = CollabConfig()
    coord = config.get_coordination_provider()

    print("Enqueueing action...")
    coord.enqueue_action("review-code", {"pr": "456"}, "agent-codex")

    print("Claiming next action...")
    action = coord.claim_action("agent-claude")
    print(f"Claimed action: {action}")


if __name__ == "__main__":
    print("=== Coordination Provider Example ===\n")

    print("1. Lock Usage:")
    example_lock_usage()

    print("\n2. Signal Usage:")
    example_signal_usage()

    print("\n3. Action Usage:")
    example_action_usage()
