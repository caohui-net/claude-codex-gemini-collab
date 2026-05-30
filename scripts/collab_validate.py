#!/usr/bin/env python3
"""Validate and repair collaboration state."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import shutil

def validate(base_dir="."):
    """Validate collaboration state consistency."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    if not collab_dir.exists():
        print("❌ Collaboration not initialized")
        return 1

    issues = []

    # Validate events.jsonl
    events_file = collab_dir / "events.jsonl"
    events = []
    if events_file.exists():
        for i, line in enumerate(events_file.read_text().strip().split('\n'), 1):
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError as e:
                issues.append(f"Line {i} malformed: {e}")

    # Check duplicate IDs
    ids = [e.get('id') for e in events]
    if len(ids) != len(set(ids)):
        issues.append(f"Duplicate event IDs detected")

    # Validate state.json
    state_file = collab_dir / "state.json"
    try:
        state = json.loads(state_file.read_text())
    except json.JSONDecodeError as e:
        issues.append(f"state.json malformed: {e}")
        state = None

    # Check state consistency
    if state and events:
        max_id = max(e.get('id', 0) for e in events)
        if state.get('last_event_id') != max_id:
            issues.append(f"Event ID mismatch: state={state.get('last_event_id')}, log max={max_id}")

    # Check stale locks
    locks_dir = collab_dir / "locks"
    if locks_dir.exists():
        for lock in locks_dir.glob("*.lock"):
            owner_file = lock / "owner.json"
            if owner_file.exists():
                try:
                    owner = json.loads(owner_file.read_text())
                    created = datetime.fromisoformat(owner.get('created_at', ''))
                    age = (datetime.now(timezone.utc) - created).total_seconds()
                    if age > 900:
                        issues.append(f"Stale lock: {lock.name} (age: {age:.0f}s)")
                except:
                    issues.append(f"Lock {lock.name} has malformed owner.json")

    # Report
    if issues:
        print(f"❌ Validation failed ({len(issues)} issues):")
        for issue in issues:
            print(f"  • {issue}")
        print(f"\nRun: /claude-codex-collab repair")
        return 1
    else:
        print(f"✓ Validation passed")
        print(f"  • {len(events)} events valid")
        print(f"  • state.json consistent")
        print(f"  • No stale locks")
        return 0

def repair(base_dir="."):
    """Attempt to repair collaboration state."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    print("🔧 Starting repair...")

    # Backup current files
    backup_dir = collab_dir / f"backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    backup_dir.mkdir(exist_ok=True)

    for f in ['state.json', 'events.jsonl']:
        src = collab_dir / f
        if src.exists():
            shutil.copy2(src, backup_dir / f)
    print(f"✓ Backed up to {backup_dir}")

    # Rebuild state from events
    events_file = collab_dir / "events.jsonl"
    events = []
    if events_file.exists():
        for line in events_file.read_text().strip().split('\n'):
            if line:
                try:
                    events.append(json.loads(line))
                except:
                    pass

    if events:
        last_event = events[-1]
        max_id = max(e.get('id', 0) for e in events)

        state = {
            "workflow_id": "claude-codex-collab-mvp",
            "current_task": last_event.get('task_id'),
            "active_agent": last_event.get('agent') if last_event.get('status') != 'completed' else 'none',
            "status": last_event.get('status', 'unknown'),
            "last_event_id": max_id,
            "updated_at": last_event.get('timestamp')
        }

        state_file = collab_dir / "state.json"
        state_file.write_text(json.dumps(state, indent=2) + '\n')
        print(f"✓ Rebuilt state.json from {len(events)} events")

    # Remove stale locks
    locks_dir = collab_dir / "locks"
    if locks_dir.exists():
        for lock in locks_dir.glob("*.lock"):
            shutil.rmtree(lock)
            print(f"✓ Removed stale lock: {lock.name}")

    print(f"✓ Repair complete")
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "repair":
        sys.exit(repair())
    else:
        sys.exit(validate())
