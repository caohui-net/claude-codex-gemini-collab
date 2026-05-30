#!/usr/bin/env python3
"""Display current collaboration state."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from collab_paths import resolve_existing_base_dir, add_base_dir_arg
from collab_event import read_events, read_state

def show_status(base_dir="."):
    """Display collaboration status."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    if not collab_dir.exists():
        print("❌ Collaboration not initialized. Run: /claude-codex-gemini-collab init")
        return 1

    # Read state
    state_file = collab_dir / "state.json"
    try:
        state = read_state(state_file)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # Read events
    events_file = collab_dir / "events.jsonl"
    events = []
    event_error = None
    if events_file.exists():
        try:
            events = read_events(events_file)
        except ValueError as e:
            event_error = str(e)

    # Display
    print(f"📊 Collaboration Status")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Workflow:      {state.get('workflow_id', 'unknown')}")
    print(f"Status:        {state.get('status', 'unknown')}")
    print(f"Active Agent:  {state.get('active_agent', 'none')}")
    print(f"Current Task:  {state.get('current_task', 'none')}")
    print(f"Last Event ID: {state.get('last_event_id', 0)}")
    print(f"Updated:       {state.get('updated_at', 'unknown')}")

    # Recent events
    if events:
        print(f"\n📝 Recent Events (last 5):")
        for event in events[-5:]:
            eid = event.get('id', '?')
            etype = event.get('type', 'unknown')
            agent = event.get('agent', '?')
            summary = event.get('summary', '')
            print(f"  [{eid}] {etype} ({agent}): {summary[:60]}")

    # Check for issues
    issues = []

    # Report event log corruption
    if event_error:
        issues.append(f"Event log malformed: {event_error}")

    if state.get('last_event_id', 0) != len(events):
        issues.append(f"Event count mismatch: state says {state.get('last_event_id')}, log has {len(events)}")

    if events:
        max_id = max(e.get('id', 0) for e in events)
        if state.get('last_event_id', 0) != max_id:
            issues.append(f"Event ID mismatch: state says {state.get('last_event_id')}, max in log is {max_id}")

    # Check for stale locks
    locks_dir = collab_dir / "locks"
    if locks_dir.exists():
        locks = list(locks_dir.glob("*.lock"))
        if locks:
            issues.append(f"Stale locks detected: {len(locks)} lock(s)")

    if issues:
        print(f"\n⚠️  Issues Detected:")
        for issue in issues:
            print(f"  • {issue}")
        print(f"\nRun: /claude-codex-gemini-collab validate")
    else:
        print(f"\n✓ No issues detected")

    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display collaboration status")
    add_base_dir_arg(parser)
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        sys.exit(show_status(base))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
