#!/usr/bin/env python3
"""Validate and repair collaboration state."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import shutil
from collab_paths import resolve_existing_base_dir, add_base_dir_arg

COMMAND_NAME = "/claude-codex-gemini-collab"


def parse_timestamp(value):
    """Parse an ISO timestamp and normalize naive values to UTC."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


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
    if not events_file.exists():
        issues.append("events.jsonl missing")
    else:
        seen_ids = set()
        for i, line in enumerate(events_file.read_text().splitlines(), 1):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as e:
                issues.append(f"Line {i} malformed: {e}")
                continue

            if not isinstance(event, dict):
                issues.append(f"Line {i} must be a JSON object")
                continue

            event_id = event.get('id')
            if not isinstance(event_id, int) or isinstance(event_id, bool):
                issues.append(f"Line {i} invalid event id: {event_id!r}")
                continue

            if event_id in seen_ids:
                issues.append(f"Duplicate event ID detected: {event_id}")
            seen_ids.add(event_id)
            events.append(event)

    # Validate state.json
    state_file = collab_dir / "state.json"
    state = None
    if not state_file.exists():
        issues.append("state.json missing")
    else:
        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError as e:
            issues.append(f"state.json malformed: {e}")
        else:
            if not isinstance(state, dict):
                issues.append("state.json must be a JSON object")
                state = None

    if state is not None and (
        not isinstance(state.get('last_event_id'), int)
        or isinstance(state.get('last_event_id'), bool)
    ):
        issues.append(f"state.json last_event_id invalid: {state.get('last_event_id')!r}")
        state = None

    # Check state consistency
    if state is not None:
        max_id = max((e.get('id', 0) for e in events), default=0)
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
                    if not isinstance(owner, dict):
                        raise ValueError("owner.json must be a JSON object")
                    created = parse_timestamp(owner.get('created_at', ''))
                    age = (datetime.now(timezone.utc) - created).total_seconds()
                    if age > 900:
                        issues.append(f"Stale lock: {lock.name} (age: {age:.0f}s)")
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    issues.append(f"Lock {lock.name} has malformed owner.json: {e}")

    # Report
    if issues:
        print(f"❌ Validation failed ({len(issues)} issues):")
        for issue in issues:
            print(f"  • {issue}")
        print(f"\nRun: {COMMAND_NAME} repair")
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

    if not collab_dir.exists():
        print("❌ Collaboration not initialized")
        return 1

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
        # Filter out scalar/non-dict events to avoid AttributeError
        events = [e for e in events if isinstance(e, dict)]

    if events:
        last_event = events[-1]
        max_id = max(e.get('id', 0) for e in events)

        state = {
            "workflow_id": "claude-codex-gemini-collab",
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
    parser = argparse.ArgumentParser(description="Validate or repair collaboration state")
    add_base_dir_arg(parser)
    parser.add_argument("command", nargs="?", default="validate", choices=["validate", "repair"])
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        if args.command == "repair":
            sys.exit(repair(base))
        else:
            sys.exit(validate(base))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
