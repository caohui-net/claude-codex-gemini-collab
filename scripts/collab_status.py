#!/usr/bin/env python3
"""Display current collaboration state."""

import json
import sys
from datetime import datetime
from pathlib import Path

def show_status(base_dir="."):
    """Display collaboration status."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    if not collab_dir.exists():
        print("❌ Collaboration not initialized. Run: /claude-codex-collab init")
        return 1

    # Read state
    state_file = collab_dir / "state.json"
    if not state_file.exists():
        print("❌ state.json not found")
        return 1

    try:
        state = json.loads(state_file.read_text())
    except json.JSONDecodeError as e:
        print(f"❌ state.json malformed: {e}")
        return 1

    # Read events
    events_file = collab_dir / "events.jsonl"
    events = []
    if events_file.exists():
        for line in events_file.read_text().strip().split('\n'):
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

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
        print(f"\nRun: /claude-codex-collab validate")
    else:
        print(f"\n✓ No issues detected")

    return 0

if __name__ == "__main__":
    sys.exit(show_status())
