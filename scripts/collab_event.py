#!/usr/bin/env python3
"""Atomic event operations for collaboration protocol."""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_paths import resolve_existing_base_dir, add_base_dir_arg
from collab_state import rebuild_state

COMMAND_NAME = "/claude-codex-gemini-collab"

STATUS_MAP = {
    "claude_ready": "claude_ready",
    "codex_ready": "codex_ready",
    "gemini_ready": "gemini_ready",
    "task_created": "task_open",
    "task_claimed": "in_progress",
    "handoff_requested": "handoff_pending",
    "handoff_accepted": "in_progress",
    "handoff_rejected": "in_progress",
    "handoff_cancelled": "in_progress",
    "handoff_timed_out": "in_progress",
    "completed": "completed",
    "blocked": "blocked",
    "independent_analysis_completed": "waiting_synthesis",
    "synthesis_completed": "completed",
    "workflow_completed": "completed",
}

ACTIVE_CLAIM_STATUSES = {
    "claimed",
    "in_progress",
    "waiting",
    "blocked",
    "timeout_candidate",
    "handoff_pending",
}
ACTIVE_CLAIM_EVENT_TYPES = {
    "task_claimed",
    "handoff_requested",
    "handoff_accepted",
    "blocked",
}
TERMINAL_CLAIM_STATUSES = {
    "completed",
    "cancelled",
}


def validate_agent_id(agent):
    """Validate agent ID format to prevent path injection and ensure ASCII-only."""
    if not agent or not isinstance(agent, str):
        raise ValueError("agent must be a non-empty string")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", agent):
        raise ValueError(f"agent ID must be ASCII alphanumeric/hyphens/underscores, 1-64 chars: {agent}")
    return agent


def get_event_task_id(event):
    """Safely extract task_id from event, handling malformed details."""
    task_id = event.get("task_id")
    if task_id:
        return task_id
    details = event.get("details")
    if isinstance(details, dict):
        return details.get("task_id")
    return None


def get_active_owner(events, task_id):
    """Return active task owner from the event log, or None if open/terminal."""
    for event in reversed(events):
        if get_event_task_id(event) != task_id:
            continue

        event_type = event.get("type")

        # Terminal events: task is no longer owned
        if event_type == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES:
            return None

        # Handoff rejection/cancellation/timeout: return ownership to requester
        if event_type in ("handoff_rejected", "handoff_cancelled", "handoff_timed_out"):
            # Find the preceding handoff_requested to get the requester
            # We're already iterating backwards, so continue from current position
            found_current = False
            for prev_event in reversed(events):
                if get_event_task_id(prev_event) != task_id:
                    continue
                # Skip until we pass the current rejection event
                if not found_current:
                    if prev_event == event:
                        found_current = True
                    continue
                # Now look for the handoff_requested
                if prev_event.get("type") == "handoff_requested":
                    return prev_event.get("agent") or "unknown"
            return "unknown"

        # Active claim events
        if event_type in ACTIVE_CLAIM_EVENT_TYPES:
            # For handoff_accepted, validate and return target_agent
            if event_type == "handoff_accepted":
                details = event.get("details", {})
                if isinstance(details, dict) and details.get("target_agent"):
                    # Validate that accepting agent matches target
                    if event.get("agent") == details["target_agent"]:
                        return details["target_agent"]
            # For handoff_requested, keep ownership with requester (two-phase handoff)
            return event.get("agent") or "unknown"

        # Fallback to status-based check
        if event.get("status") in ACTIVE_CLAIM_STATUSES:
            return event.get("agent") or "unknown"

    return None


def is_terminal_event(event, task_id):
    """Check if event represents terminal state for task."""
    if get_event_task_id(event) != task_id:
        return False
    return event.get("type") == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES


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
    validate_agent_id(agent)
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

    # Validate agent before any operations
    try:
        validate_agent_id(agent)
    except ValueError as e:
        print(f"❌ Invalid agent ID: {e}")
        return 1

    # Validate blocked events require reason
    if event_type == "blocked":
        if not details or not isinstance(details, dict) or not details.get("reason"):
            print(f"❌ Event type 'blocked' requires reason in details")
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

        # Validate handoff_requested: task must exist and agent must be owner
        if event_type == "handoff_requested" and task_id:
            # Enforce target_agent field
            if not isinstance(details, dict) or not details.get("target_agent"):
                print(f"❌ Cannot handoff: target_agent required in details")
                return 1

            task_exists = any(
                e.get('type') == 'task_created' and get_event_task_id(e) == task_id
                for e in events
            )
            if not task_exists:
                print(f"❌ Cannot handoff: task {task_id} not found in events")
                return 1

            # Check if task is already terminal
            task_terminal = any(is_terminal_event(e, task_id) for e in events)
            if task_terminal:
                print(f"❌ Cannot handoff: task {task_id} already in terminal state")
                return 1

            # Check if agent is current owner
            current_owner = get_active_owner(events, task_id)
            if current_owner and current_owner != agent:
                print(f"❌ Cannot handoff: task {task_id} owned by {current_owner}, not {agent}")
                return 1

        # Validate handoff_accepted: must have pending handoff_requested
        if event_type == "handoff_accepted" and task_id:
            # Find most recent handoff_requested for this task
            pending_handoff = None
            for e in reversed(events):
                if get_event_task_id(e) != task_id:
                    continue
                if e.get('type') == 'handoff_requested':
                    pending_handoff = e
                    break
                # Stop if we hit a terminal or accepted handoff
                if e.get('type') in ['handoff_accepted', 'handoff_rejected', 'handoff_cancelled', 'completed']:
                    break

            if not pending_handoff:
                print(f"❌ Cannot accept handoff: no pending handoff_requested for task {task_id}")
                return 1

            # Validate agent is the target
            target_agent = pending_handoff.get('details', {}).get('target_agent')
            if target_agent != agent:
                print(f"❌ Cannot accept handoff: task {task_id} handoff target is {target_agent}, not {agent}")
                return 1

        # Validate completed: task must exist, not be terminal, and agent must be owner
        # Normalize task_id from top-level or details (Task #27 fix)
        effective_task_id = task_id or (details.get("task_id") if isinstance(details, dict) else None)

        # Reject taskless completed (P2 Final Hardening)
        if event_type == "completed" and not effective_task_id:
            print("❌ Cannot append 'completed' event without task_id")
            print("   Use 'workflow_completed' for workflow-level completion")
            return 1

        # Reject workflow_completed with task_id (P2 Final Hardening)
        if event_type == "workflow_completed":
            if task_id or (details and isinstance(details, dict) and details.get("task_id")):
                print("❌ Cannot append 'workflow_completed' with task_id")
                print("   Use 'completed' for task completion")
                return 1

            # Reject workflow_completed if any non-terminal task exists
            for e in events:
                if e.get('type') == 'task_created':
                    tid = get_event_task_id(e)
                    if tid:
                        # Check if this task is terminal
                        task_is_terminal = any(
                            is_terminal_event(ev, tid) for ev in events
                        )
                        if not task_is_terminal:
                            print(f"❌ Cannot append 'workflow_completed': task {tid} is not terminal")
                            print("   Complete or cancel all tasks before workflow completion")
                            return 1

        if event_type == "completed" and effective_task_id:
            task_created = False
            task_terminal = False

            for e in events:
                if e.get('type') == 'task_created' and get_event_task_id(e) == effective_task_id:
                    task_created = True
                # Check terminal state using both type and status (Task #26 fix)
                if is_terminal_event(e, effective_task_id):
                    task_terminal = True

            if not task_created:
                print(f"❌ Cannot complete: task {effective_task_id} not found in events")
                return 1
            if task_terminal:
                print(f"❌ Cannot complete: task {effective_task_id} already in terminal state")
                return 1

            # Use get_active_owner() for consistent ownership check (Task #25 fix)
            current_owner = get_active_owner(events, effective_task_id)
            if current_owner and current_owner != agent:
                print(f"❌ Cannot complete: task {effective_task_id} owned by {current_owner}, not {agent}")
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

        # Validate event schema (P4-lite: minimal whitelist)
        required_fields = ["id", "timestamp", "type", "agent", "summary"]
        missing_fields = [f for f in required_fields if f not in event or event[f] is None]
        if missing_fields:
            print(f"❌ Event schema validation failed: missing required fields {missing_fields}")
            return 1

        # Append to events.jsonl
        with events_file.open('a') as f:
            f.write(json.dumps(event) + '\n')

        # Rebuild state using centralized reducer
        events_with_new = events + [event]
        state = rebuild_state(events_with_new)

        # Add workflow_id for compatibility
        state["workflow_id"] = "claude-codex-gemini-collab"

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
    parser.add_argument("--target-agent", help="Target agent for handoff (optional)")
    parser.add_argument("--reason", help="Reason for state transition (required for blocked events)")
    parser.add_argument("--log-file", help="Path to log file to attach")
    args = parser.parse_args()

    try:
        base = resolve_existing_base_dir(args.base_dir)
        task_id = None if args.task_id == "none" else args.task_id
        artifacts = json.loads(args.artifacts) if args.artifacts else None

        # Build details dict with reason, logs, and target_agent
        details = {}
        if args.target_agent:
            # Validate target_agent
            try:
                validate_agent_id(args.target_agent)
            except ValueError as e:
                print(f"❌ Invalid target agent: {e}")
                sys.exit(1)
            details["target_agent"] = args.target_agent

        if args.reason:
            details["reason"] = args.reason

        if args.log_file:
            # Store log file reference
            details["logs"] = [args.log_file]

        # Validate blocked events require reason
        if args.event_type == "blocked" and not args.reason:
            print(f"❌ Event type 'blocked' requires --reason parameter")
            sys.exit(1)

        details = details if details else None
        sys.exit(append_event(base, args.event_type, args.agent, task_id, args.summary, artifacts, details))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
