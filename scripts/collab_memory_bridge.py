#!/usr/bin/env python3
"""Python wrapper for collab_memory_bridge.mjs — sync events.jsonl → agentmemory."""
import subprocess
import sys
from pathlib import Path

BRIDGE_MJS = Path(__file__).parent / "collab_memory_bridge.mjs"


def sync_events(base_dir=".") -> int:
    """Sync new events to agentmemory. Returns 0 on success."""
    result = subprocess.run(
        ["node", str(BRIDGE_MJS), str(base_dir)],
        capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0 and result.stderr:
        print(f"⚠️  agentmemory bridge: {result.stderr.rstrip()}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(sync_events(base))
