#!/usr/bin/env python3
"""Task lifecycle operations."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_event import append_event, acquire_lock, release_lock

def create_task(base_dir, description):
    """Create new collaboration task."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    # Generate task ID
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = list((collab_dir / "tasks").glob(f"TASK-{timestamp}-*.md"))
    task_num = len(existing) + 1
    task_id = f"TASK-{timestamp}-{task_num:02d}"

    # Create task document
    task_file = collab_dir / "tasks" / f"{task_id}-{description[:30].replace(' ', '-').lower()}.md"
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
    task_file.write_text(task_content)

    # Append event
    append_event(base_dir, "task_created", "claude", task_id,
                 f"Created task: {description}", [str(task_file)])

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
        # Check task not already claimed
        events_file = collab_dir / "events.jsonl"
        events = []
        if events_file.exists() and events_file.stat().st_size > 0:
            for line in events_file.read_text().strip().split('\n'):
                if line:
                    event = json.loads(line)
                    events.append(event)
                    if (event.get('task_id') == task_id and
                        event.get('type') in ['task_claimed', 'in_progress'] and
                        event.get('status') not in ['completed', 'cancelled']):
                        release_lock(collab_dir)
                        print(f"❌ Task {task_id} already claimed by {event.get('agent')}")
                        return 1

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

        release_lock(collab_dir)
        print(f"✓ Task {task_id} claimed by {agent}")
        print(f"✓ Event {next_id} appended: task_claimed")
        return 0

    except Exception as e:
        release_lock(collab_dir)
        print(f"❌ Error: {e}")
        return 1

def complete_task(base_dir, task_id, agent="claude"):
    """Mark task completed."""
    return append_event(base_dir, "completed", agent, task_id,
                       f"Completed task {task_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: collab_task.py <create|claim|complete> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "create" and len(sys.argv) >= 3:
        sys.exit(create_task(".", sys.argv[2]))
    elif cmd == "claim" and len(sys.argv) >= 3:
        agent = sys.argv[3] if len(sys.argv) > 3 else "claude"
        sys.exit(claim_task(".", sys.argv[2], agent))
    elif cmd == "complete" and len(sys.argv) >= 3:
        agent = sys.argv[3] if len(sys.argv) > 3 else "claude"
        sys.exit(complete_task(".", sys.argv[2], agent))
    else:
        print("Invalid command")
        sys.exit(1)
