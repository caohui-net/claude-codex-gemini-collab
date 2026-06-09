#!/usr/bin/env python3
"""Initialize Claude-Codex collaboration directory structure."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_paths import resolve_init_base_dir, add_base_dir_arg

def init_collaboration(base_dir=".", source="cwd"):
    """Initialize collaboration directory structure."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".collab"

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
            "workflow_id": "claude-codex-gemini-collab",
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

    # Copy protocol.md from assets
    protocol_file = collab_dir / "protocol.md"
    if not protocol_file.exists():
        # Copy from assets/protocol.md
        script_dir = Path(__file__).parent
        assets_protocol = script_dir.parent / "assets" / "protocol.md"
        if assets_protocol.exists():
            protocol_file.write_text(assets_protocol.read_text())
        else:
            # Fallback: minimal protocol template
            protocol_file.write_text("""# Claude-Codex-Gemini Collaboration Protocol

Version: 0.3
Status: active

See full protocol documentation for details.
""")

    print(f"✓ Collaboration directory initialized: {collab_dir}")
    print(f"✓ Base directory: {base} (source: {source})")
    print(f"✓ Created: state.json, events.jsonl, protocol.md")
    print(f"✓ Created subdirectories: tasks/, artifacts/, locks/")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize collaboration directory")
    add_base_dir_arg(parser)
    args = parser.parse_args()

    base, source = resolve_init_base_dir(args.base_dir)
    sys.exit(init_collaboration(base, source))
