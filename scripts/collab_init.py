#!/usr/bin/env python3
"""Initialize Claude-Codex collaboration directory structure."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

def init_collaboration(base_dir="."):
    """Initialize collaboration directory structure."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    # Create directory structure
    dirs = [
        collab_dir,
        collab_dir / "tasks",
        collab_dir / "artifacts",
        collab_dir / "locks",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Initialize state.json
    state_file = collab_dir / "state.json"
    if not state_file.exists():
        state = {
            "workflow_id": "claude-codex-collab-mvp",
            "current_task": None,
            "active_agent": "none",
            "status": "initialized",
            "last_event_id": 0,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        state_file.write_text(json.dumps(state, indent=2) + "\n")

    # Initialize events.jsonl
    events_file = collab_dir / "events.jsonl"
    if not events_file.exists():
        events_file.touch()

    # Copy protocol.md template
    protocol_file = collab_dir / "protocol.md"
    if not protocol_file.exists():
        # Copy from current protocol if exists, otherwise create minimal
        current_protocol = collab_dir.parent.parent / ".omc" / "collaboration" / "protocol.md"
        if current_protocol.exists():
            protocol_file.write_text(current_protocol.read_text())
        else:
            # Minimal protocol template
            protocol_file.write_text("""# Claude-Codex Collaboration Protocol

Version: 0.2
Status: active

See full protocol documentation for details.
""")

    print(f"✓ Collaboration directory initialized: {collab_dir}")
    print(f"✓ Created: state.json, events.jsonl, protocol.md")
    print(f"✓ Created subdirectories: tasks/, artifacts/, locks/")
    return 0

if __name__ == "__main__":
    sys.exit(init_collaboration())
