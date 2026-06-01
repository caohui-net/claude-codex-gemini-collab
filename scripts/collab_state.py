#!/usr/bin/env python3
"""Pure state reduction functions for collaboration protocol."""

# Status mappings
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


def get_event_task_id(event):
    """Extract task_id from event."""
    task_id = event.get("task_id")
    if task_id:
        return task_id
    details = event.get("details")
    if isinstance(details, dict):
        return details.get("task_id")
    return None


def is_terminal_event(event, task_id):
    """Check if event marks task as terminal."""
    if get_event_task_id(event) != task_id:
        return False
    return event.get("type") == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES


def get_active_owner(events, task_id):
    """Return active task owner from event log, or None if open/terminal."""
    for event in reversed(events):
        if get_event_task_id(event) != task_id:
            continue

        event_type = event.get("type")

        # Terminal events
        if event_type == "completed" or event.get("status") in TERMINAL_CLAIM_STATUSES:
            return None

        # Handoff rejection/cancellation/timeout: return to requester
        if event_type in ("handoff_rejected", "handoff_cancelled", "handoff_timed_out"):
            found_current = False
            for prev_event in reversed(events):
                if get_event_task_id(prev_event) != task_id:
                    continue
                if not found_current:
                    if prev_event == event:
                        found_current = True
                    continue
                if prev_event.get("type") == "handoff_requested":
                    return prev_event.get("agent") or "unknown"
            return "unknown"

        # Active claim events
        if event_type in ACTIVE_CLAIM_EVENT_TYPES:
            if event_type == "handoff_accepted":
                details = event.get("details", {})
                if isinstance(details, dict) and details.get("target_agent"):
                    if event.get("agent") == details["target_agent"]:
                        return details["target_agent"]
            return event.get("agent") or "unknown"

        # Fallback to status-based check
        if event.get("status") in ACTIVE_CLAIM_STATUSES:
            return event.get("agent") or "unknown"

    return None


def rebuild_state(events):
    """Rebuild state.json from events.jsonl."""
    if not events:
        return {
            "last_event_id": 0,
            "status": "initialized",
            "current_task": None,
            "active_agent": None,
        }

    last_event = events[-1]
    last_event_id = last_event.get("id", 0)

    # Find current task and active agent
    current_task = None
    active_agent = None

    # Look for most recent non-terminal task
    for event in reversed(events):
        task_id = get_event_task_id(event)
        if task_id and not is_terminal_event(event, task_id):
            owner = get_active_owner(events, task_id)
            if owner:
                current_task = task_id
                active_agent = owner
                break

    # Determine workflow status
    status = STATUS_MAP.get(last_event.get("type"), "initialized")

    return {
        "last_event_id": last_event_id,
        "status": status,
        "current_task": current_task,
        "active_agent": active_agent,
    }
