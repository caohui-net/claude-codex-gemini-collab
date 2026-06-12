#!/usr/bin/env python3
"""Task lifecycle operations."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_event import append_event, acquire_lock, release_lock, read_state, write_state_atomically, read_events, validate_agent_id, get_event_task_id, get_active_owner, TERMINAL_CLAIM_STATUSES
from collab_paths import resolve_existing_base_dir, add_base_dir_arg

def can_claim(events, task_id, agent):
    """Return (can_claim, reason, owner) for an atomic claim attempt."""
    task_exists = any(
        event.get("type") == "task_created" and get_event_task_id(event) == task_id
        for event in events
    )
    if not task_exists:
        return False, f"Task {task_id} not found", None

    for event in reversed(events):
        if get_event_task_id(event) == task_id and (
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
    collab_dir = base / ".collab"

    # Acquire lock to ensure atomic task ID generation
    if not acquire_lock(collab_dir, "claude", "none", "create task"):
        print("❌ Failed to acquire journal lock")
        return 1

    try:
        events_file = collab_dir / "events.jsonl"
        state_file = collab_dir / "state.json"

        # Validate state before creating task
        try:
            events = read_events(events_file)
            state = read_state(state_file)
        except ValueError as e:
            print(f"❌ Validation failed: {e}")
            return 1

        # Generate task ID from next event ID (concurrency-safe)
        next_id = max((e.get('id', 0) for e in events if e.get('id') is not None), default=0) + 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        task_id = f"TASK-{timestamp}-{next_id:02d}"

        # Check for task_id collision
        task_exists_in_events = any(
            event.get("type") == "task_created" and get_event_task_id(event) == task_id
            for event in events
        )
        if task_exists_in_events:
            print(f"❌ Task ID collision: {task_id} already exists in events")
            return 1

        tasks_dir = collab_dir / "tasks"
        if tasks_dir.exists():
            existing_files = list(tasks_dir.glob(f"{task_id}-*.md"))
            if existing_files:
                print(f"❌ Task ID collision: {task_id} file already exists")
                return 1

        # Prepare task document
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

        # Create event
        event = {
            "id": next_id,
            "type": "task_created",
            "agent": "claude",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": f"Created task: {description}",
            "task_id": task_id,
            "artifacts": [str(task_file)],
            "status": "task_open"
        }

        # Append event
        with events_file.open('a') as f:
            f.write(json.dumps(event) + '\n')

        # Update state atomically
        state["last_event_id"] = next_id
        state["status"] = "task_open"
        state["current_task"] = task_id
        state["updated_at"] = event["timestamp"]

        write_state_atomically(collab_dir, "claude", state)

        # Write task file only after successful event append
        task_file.write_text(task_content)

        print(f"✓ Event {next_id} appended: task_created")
        print(f"✓ State updated: status=task_open, last_event_id={next_id}")
        print(f"✓ Task created: {task_id}")
        print(f"✓ File: {task_file}")
        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        release_lock(collab_dir, agent="claude")

def claim_task(base_dir, task_id, agent="claude"):
    """Claim task atomically."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".collab"

    # Validate agent before any operations
    try:
        validate_agent_id(agent)
    except ValueError as e:
        print(f"❌ Invalid agent ID: {e}")
        return 1

    # Acquire lock
    if not acquire_lock(collab_dir, agent, task_id, "claim task"):
        return 1

    try:
        events_file = collab_dir / "events.jsonl"
        state_file = collab_dir / "state.json"

        # Validate state BEFORE appending event
        try:
            events = read_events(events_file)
            state = read_state(state_file)
        except ValueError as e:
            print(f"❌ Validation failed: {e}")
            return 1

        allowed, reason, owner = can_claim(events, task_id, agent)
        if not allowed:
            print(f"❌ {reason}")
            return 1

        if owner == agent:
            print(f"✓ Task {task_id} already claimed by {agent}")
            print("✓ No new event appended")
            return 0

        # Append claim event atomically while holding lock
        next_id = max((e.get('id', 0) for e in events if e.get('id') is not None), default=0) + 1
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

        # Update state atomically
        state["last_event_id"] = next_id
        state["status"] = "in_progress"
        state["current_task"] = task_id
        state["active_agent"] = agent
        state["updated_at"] = event["timestamp"]

        write_state_atomically(collab_dir, agent, state)

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

def list_tasks(base_dir):
    """List all tasks with their status."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".collab"
    events_file = collab_dir / "events.jsonl"

    try:
        events = read_events(events_file)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    tasks = {}
    for event in events:
        if event.get('type') == 'task_created':
            task_id = get_event_task_id(event)
            if task_id:
                tasks[task_id] = {'id': task_id, 'summary': event.get('summary', ''), 'status': 'open', 'owner': None}

    for task_id in tasks:
        owner = get_active_owner(events, task_id)
        if owner:
            tasks[task_id]['owner'] = owner
            tasks[task_id]['status'] = 'in_progress'
        for event in reversed(events):
            if get_event_task_id(event) == task_id and event.get('type') == 'completed':
                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['owner'] = event.get('agent')
                break

    print(f"📋 Tasks ({len(tasks)} total)")
    for task_id, info in sorted(tasks.items()):
        icon = "✓" if info['status'] == 'completed' else "⏳" if info['status'] == 'in_progress' else "○"
        owner = f" [{info['owner']}]" if info['owner'] else ""
        print(f"{icon} {task_id}: {info['summary'][:50]}{owner}")
    return 0

def current_task(base_dir):
    """Show current task."""
    base = Path(base_dir).resolve()
    state_file = base / ".collab" / "state.json"
    try:
        state = read_state(state_file)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    current = state.get('current_task')
    if current:
        print(f"📌 Current: {current} [{state.get('active_agent', 'none')}] ({state.get('status', 'unknown')})")
    else:
        print("No current task")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task lifecycle operations")
    add_base_dir_arg(parser)
    parser.add_argument("command", choices=["create", "claim", "complete", "list", "current"])
    parser.add_argument("task_arg", nargs="?", help="Task description (create) or task ID (claim/complete)")
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
        elif args.command == "list":
            sys.exit(list_tasks(base))
        elif args.command == "current":
            sys.exit(current_task(base))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
