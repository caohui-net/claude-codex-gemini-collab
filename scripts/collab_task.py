#!/usr/bin/env python3
"""Task lifecycle operations."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_event import append_event, acquire_lock, release_lock
from collab_paths import resolve_existing_base_dir, add_base_dir_arg

ACTIVE_CLAIM_STATUSES = {
    "claimed",
    "in_progress",
    "waiting",
    "blocked",
    "timeout_candidate",
}
ACTIVE_CLAIM_EVENT_TYPES = {
    "task_claimed",
    "handoff_requested",
    "blocked",
}
TERMINAL_CLAIM_STATUSES = {
    "completed",
    "cancelled",
}

def get_task_id(event):
    """Return task_id from top-level field, falling back to details.task_id."""
    details = event.get("details")
    if not isinstance(details, dict):
        details = {}
    return event.get("task_id") or details.get("task_id")

def read_events(events_file):
    """Read events.jsonl and fail on malformed lines or duplicate ids."""
    events = []
    seen_ids = set()
    if not events_file.exists() or events_file.stat().st_size == 0:
        return events

    for line_no, line in enumerate(events_file.read_text().splitlines(), 1):
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"events.jsonl line {line_no} malformed: {e}")

        event_id = event.get("id")
        if event_id in seen_ids:
            raise ValueError(f"events.jsonl has duplicate event id: {event_id}")
        seen_ids.add(event_id)
        events.append(event)

    return events

def get_active_owner(events, task_id):
    """Return active task owner from the event log, or None if open/terminal."""
    for event in reversed(events):
        if get_task_id(event) != task_id:
            continue

        if event.get("type") == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES:
            return None

        if event.get("status") in ACTIVE_CLAIM_STATUSES:
            return event.get("agent") or "unknown"

        if event.get("type") in ACTIVE_CLAIM_EVENT_TYPES:
            return event.get("agent") or "unknown"

    return None

def can_claim(events, task_id, agent):
    """Return (can_claim, reason, owner) for an atomic claim attempt."""
    task_exists = any(
        event.get("type") == "task_created" and get_task_id(event) == task_id
        for event in events
    )
    if not task_exists:
        return False, f"Task {task_id} not found", None

    for event in reversed(events):
        if get_task_id(event) == task_id and (
            event.get("type") == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES
        ):
            return False, f"Task {task_id} already completed", None

    owner = get_active_owner(events, task_id)
    if owner is None:
        return True, "Task is open", None
    if owner == agent:
        return True, "Same agent (idempotent)", owner
    return False, f"Task {task_id} already claimed by {owner}", owner

def create_task(base_dir, description):
    """Create new collaboration task."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    # Generate task ID
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = list((collab_dir / "tasks").glob(f"TASK-{timestamp}-*.md"))
    task_num = len(existing) + 1
    task_id = f"TASK-{timestamp}-{task_num:02d}"

    # Prepare task document
    # Sanitize description for filename (remove path separators and special chars)
    safe_desc = description[:30].replace('/', '-').replace('\\', '-').replace(' ', '-').lower()
    task_file = collab_dir / "tasks" / f"{task_id}-{safe_desc}.md"
    task_content = f"""---
task_id: {task_id}
owner: claude
assignee: none
status: open
created_at: {datetime.now(timezone.utc).isoformat()}
updated_at: {datetime.now(timezone.utc).isoformat()}
priority: normal
---

# Task: {description}

**Task ID:** {task_id}
**Status:** open

## Objective

{description}

## Acceptance Criteria

- [ ] Task completed as described
"""

    # Append event first
    result = append_event(base_dir, "task_created", "claude", task_id,
                          f"Created task: {description}", [str(task_file)])

    if result != 0:
        print(f"❌ Failed to create task: event append failed")
        return result

    # Write task file only after successful event append
    task_file.write_text(task_content)

    print(f"✓ Task created: {task_id}")
    print(f"✓ File: {task_file}")
    return 0

def claim_task(base_dir, task_id, agent="claude"):
    """Claim task atomically."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    # Acquire lock
    if not acquire_lock(collab_dir, agent, task_id, "claim task"):
        return 1

    try:
        events_file = collab_dir / "events.jsonl"
        events = read_events(events_file)

        allowed, reason, owner = can_claim(events, task_id, agent)
        if not allowed:
            print(f"❌ {reason}")
            return 1

        if owner == agent:
            print(f"✓ Task {task_id} already claimed by {agent}")
            print("✓ No new event appended")
            return 0

        # Append claim event atomically while holding lock
        next_id = max((e.get('id', 0) for e in events), default=0) + 1
        event = {
            "id": next_id,
            "type": "task_claimed",
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": f"{agent} claimed task {task_id}",
            "task_id": task_id,
            "status": "in_progress"
        }

        with events_file.open('a') as f:
            f.write(json.dumps(event) + '\n')

        # Update state
        state_file = collab_dir / "state.json"
        state = json.loads(state_file.read_text())
        state["last_event_id"] = next_id
        state["status"] = "in_progress"
        state["current_task"] = task_id
        state["active_agent"] = agent
        state["updated_at"] = event["timestamp"]

        temp_file = collab_dir / f"state.json.tmp.{agent}"
        temp_file.write_text(json.dumps(state, indent=2) + '\n')
        temp_file.replace(state_file)

        print(f"✓ Task {task_id} claimed by {agent}")
        print(f"✓ Event {next_id} appended: task_claimed")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        release_lock(collab_dir, agent=agent, task_id=task_id)

def complete_task(base_dir, task_id, agent="claude"):
    """Mark task completed."""
    return append_event(base_dir, "completed", agent, task_id,
                       f"Completed task {task_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task lifecycle operations")
    add_base_dir_arg(parser)
    parser.add_argument("command", choices=["create", "claim", "complete"])
    parser.add_argument("task_arg", help="Task description (create) or task ID (claim/complete)")
    parser.add_argument("agent", nargs="?", default="claude", help="Agent name (claim/complete)")
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        if args.command == "create":
            sys.exit(create_task(base, args.task_arg))
        elif args.command == "claim":
            sys.exit(claim_task(base, args.task_arg, args.agent))
        elif args.command == "complete":
            sys.exit(complete_task(base, args.task_arg, args.agent))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
