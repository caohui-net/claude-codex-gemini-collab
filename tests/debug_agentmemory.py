#!/usr/bin/env python3
"""Debug agentmemory trigger responses."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.coordination.agentmemory import AgentMemoryCoordination
import json

def debug_lease():
    """Debug lease operations and print raw responses."""
    coord = AgentMemoryCoordination("ws://localhost:49134")

    print("=== Step 1: Create an action ===")
    try:
        result = coord._trigger("mem::action-create", {
            "title": "test-action",
            "description": "Test action for lease testing"
        })
        print(f"Action create result: {json.dumps(result, indent=2)}")
        action_id = result.get("action", {}).get("id") if result else None
        print(f"Action ID: {action_id}")
    except Exception as e:
        print(f"Error creating action: {e}")
        action_id = None

    if not action_id:
        print("Failed to create action, aborting")
        return

    print(f"\n=== Step 2: Acquire lease for action {action_id} ===")
    try:
        result = coord._trigger("mem::lease-acquire", {
            "actionId": action_id,
            "agentId": "test-agent",
            "ttlMs": 60000
        })
        print(f"Lease acquire result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error acquiring lease: {e}")

    print(f"\n=== Step 3: Release lease for action {action_id} ===")
    try:
        result = coord._trigger("mem::lease-release", {
            "actionId": action_id,
            "agentId": "test-agent"
        })
        print(f"Lease release result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error releasing lease: {e}")

if __name__ == "__main__":
    debug_lease()
