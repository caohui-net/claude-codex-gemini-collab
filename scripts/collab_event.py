#!/usr/bin/env python3
"""Atomic event operations for collaboration protocol."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_paths import resolve_existing_base_dir, add_base_dir_arg

COMMAND_NAME = "/claude-codex-gemini-collab"

STATUS_MAP = {
    "task_created": "task_open",
    "task_claimed": "in_progress",
    "handoff_requested": "waiting",
    "completed": "completed",
    "blocked": "blocked",
    "independent_analysis_completed": "waiting_synthesis",
    "synthesis_completed": "completed",
}


def read_events(events_file):
    """Read and validate events.jsonl before normal writes."""
    events = []
    seen_ids = set()
    if not events_file.exists():
        raise ValueError("events.jsonl missing")
    if events_file.stat().st_size == 0:
        return events

    for line_no, line in enumerate(events_file.read_text().splitlines(), 1):
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"events.jsonl line {line_no} malformed: {e}") from e

        if not isinstance(event, dict):
            raise ValueError(f"events.jsonl line {line_no} must be a JSON object")

        event_id = event.get("id")
        if not isinstance(event_id, int) or isinstance(event_id, bool):
            raise ValueError(f"events.jsonl line {line_no} has invalid event id: {event_id!r}")
        if event_id in seen_ids:
            raise ValueError(f"events.jsonl has duplicate event id: {event_id}")
        seen_ids.add(event_id)
        events.append(event)

    return events


def read_state(state_file):
    """Read and validate state.json before normal writes."""
    if not state_file.exists():
        raise ValueError("state.json missing")

    try:
        state = json.loads(state_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"state.json malformed: {e}") from e

    if not isinstance(state, dict):
        raise ValueError("state.json must be a JSON object")

    return state


def write_state_atomically(collab_dir, agent, state):
    """Write state through a validated temp file and atomic rename."""
    state_file = collab_dir / "state.json"
    temp_file = collab_dir / f"state.json.tmp.{agent}"
    temp_file.write_text(json.dumps(state, indent=2) + '\n')

    try:
        written_state = json.loads(temp_file.read_text())
    except json.JSONDecodeError as e:
        temp_file.unlink(missing_ok=True)
        raise ValueError(f"temporary state JSON malformed: {e}") from e

    if not isinstance(written_state, dict):
        temp_file.unlink(missing_ok=True)
        raise ValueError("temporary state JSON must be an object")

    temp_file.replace(state_file)

def acquire_lock(collab_dir, agent, task_id, reason):
    """Acquire journal lock atomically using mkdir."""
    lock_dir = collab_dir / "locks" / "journal.lock"

    try:
        lock_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # Lock exists, check if stale
        owner_file = lock_dir / "owner.json"
        if owner_file.exists():
            try:
                owner = json.loads(owner_file.read_text())
                created = datetime.fromisoformat(owner.get('created_at', ''))
                age = (datetime.now(timezone.utc) - created).total_seconds()
                if age > 900:  # 15 minutes
                    print(f"⚠️  Stale lock detected (age: {age:.0f}s). Run: {COMMAND_NAME} repair")
                else:
                    print(f"❌ Lock held by {owner.get('agent')} for task {owner.get('task_id')}")
            except:
                print(f"❌ Lock exists but owner.json malformed")
        return False

    # Write owner info
    owner = {
        "agent": agent,
        "task_id": task_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason
    }
    (lock_dir / "owner.json").write_text(json.dumps(owner, indent=2))
    return True

def release_lock(collab_dir, agent=None, task_id=None):
    """Release journal lock, optionally verifying the lock owner first."""
    lock_dir = collab_dir / "locks" / "journal.lock"
    if not lock_dir.exists():
        return

    if agent is not None or task_id is not None:
        owner_file = lock_dir / "owner.json"
        if not owner_file.exists():
            raise ValueError(f"Lock {lock_dir} has no owner.json - cannot verify owner")

        try:
            owner = json.loads(owner_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(
                f"Lock {lock_dir} has malformed owner.json: {e}. "
                "Cannot release. Use collab_validate.py repair."
            )

        if agent is not None and owner.get("agent") != agent:
            raise ValueError(
                f"Lock {lock_dir} held by agent={owner.get('agent')!r}, "
                f"cannot release by agent={agent!r}"
            )

        if task_id is not None and owner.get("task_id") != task_id:
            raise ValueError(
                f"Lock {lock_dir} held for task={owner.get('task_id')!r}, "
                f"cannot release for task={task_id!r}"
            )

    shutil.rmtree(lock_dir)

def append_event(base_dir, event_type, agent, task_id, summary, artifacts=None, details=None):
    """Append event atomically with journal lock."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    if not collab_dir.exists():
        print("❌ Collaboration not initialized")
        return 1

    # Acquire lock
    if not acquire_lock(collab_dir, agent, task_id, f"append {event_type} event"):
        print("❌ Failed to acquire journal lock")
        return 1

    try:
        # Read and validate events.jsonl/state.json before any write.
        events_file = collab_dir / "events.jsonl"
        state_file = collab_dir / "state.json"
        try:
            events = read_events(events_file)
            state = read_state(state_file)
        except ValueError as e:
            print(f"❌ Validation failed: {e}")
            print(f"Run: {COMMAND_NAME} repair")
            return 1

        # Validate handoff_requested: task must exist
        if event_type == "handoff_requested" and task_id:
            task_exists = any(
                e.get('type') == 'task_created' and
                (e.get('task_id') == task_id or e.get('details', {}).get('task_id') == task_id)
                for e in events
            )
            if not task_exists:
                print(f"❌ Cannot handoff: task {task_id} not found in events")
                return 1

        # Compute next ID from log
        next_id = max((e.get('id', 0) for e in events), default=0) + 1

        # Create event
        event = {
            "id": next_id,
            "type": event_type,
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary
        }
        if task_id:
            event["task_id"] = task_id
        if artifacts:
            event["artifacts"] = artifacts
        if details:
            event["details"] = details

        # Determine status from event type
        event["status"] = STATUS_MAP.get(event_type, "in_progress")

        # Append to events.jsonl
        with events_file.open('a') as f:
            f.write(json.dumps(event) + '\n')

        # Update state.json atomically
        state["last_event_id"] = next_id
        state["status"] = event["status"]
        state["updated_at"] = event["timestamp"]
        if task_id:
            state["current_task"] = task_id
        if event_type == "completed":
            state["active_agent"] = "none"

        write_state_atomically(collab_dir, agent, state)

        print(f"✓ Event {next_id} appended: {event_type}")
        print(f"✓ State updated: status={event['status']}, last_event_id={next_id}")

        return 0

    finally:
        release_lock(collab_dir, agent=agent)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Append event to collaboration log")
    add_base_dir_arg(parser)
    parser.add_argument("event_type", help="Event type")
    parser.add_argument("agent", help="Agent name")
    parser.add_argument("task_id", help="Task ID (or 'none')")
    parser.add_argument("summary", help="Event summary")
    parser.add_argument("artifacts", nargs="?", help="Artifacts JSON")
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        task_id = None if args.task_id == "none" else args.task_id
        artifacts = json.loads(args.artifacts) if args.artifacts else None
        sys.exit(append_event(base, args.event_type, args.agent, task_id, args.summary, artifacts))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
