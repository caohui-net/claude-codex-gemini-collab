#!/usr/bin/env python3
"""Debug signal operations."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.coordination.agentmemory import AgentMemoryCoordination
import json
import time

def debug_signal():
    coord = AgentMemoryCoordination("ws://localhost:49134")

    print("=== Step 1: Send signal ===")
    try:
        result = coord._trigger("mem::signal-send", {
            "from": "sender-agent",
            "to": "test-agent",
            "content": "test message",
            "type": "test-signal",
            "body": {"data": "hello"}
        })
        print(f"Send result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error sending: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Step 2: Read signals immediately ===")
    try:
        result = coord._trigger("mem::signal-read", {
            "agentId": "test-agent",
            "markRead": True
        })
        print(f"Read result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error reading: {e}")

    print("\n=== Step 3: Read again after 1 second ===")
    time.sleep(1)
    try:
        result = coord._trigger("mem::signal-read", {
            "agentId": "test-agent",
            "markRead": False
        })
        print(f"Read result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error reading: {e}")

if __name__ == "__main__":
    debug_signal()
