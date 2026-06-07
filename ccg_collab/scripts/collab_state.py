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
    # Discussion events (ownership-neutral)
    "discussion_started": "discussion",
    "discussion_message": "discussion",
    "discussion_round_start": "discussion",
    "discussion_round_end": "discussion",
    "discussion_concluded": "discussion",
    # Automatic routing events
    "classify_requested": "routing",
    "route_decided": "routing",
    "manual_override": "routing",
    # Execution and audit events
    "code_completed": "ready_for_audit",
    "audit_started": "auditing",
    "audit_completed": "audit_completed",
    "audit_failed": "audit_failed",
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


# Task-level persistence functions

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List


def get_task_state_file(base_dir: Path, task_id: str) -> Path:
    """Get state file path for task."""
    state_dir = base_dir / ".omc" / "collaboration" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{task_id}.json"


def init_task_state(base_dir: Path, task_id: str, topic: str, participants: List[str],
                    max_rounds: int = 3, hard_max_rounds: int = 10) -> Dict:
    """Initialize new task state."""
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "task_id": task_id,
        "topic": topic,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "limits": {"max_rounds": max_rounds, "hard_max_rounds": hard_max_rounds},
        "rounds": [],
        "final_consensus": {"reached": False, "decision": None, "blocking_issues": [], "round_number": None},
        "failures": [],
        "retry_attempts": [],
        "artifacts": {"directory": ".omc/collaboration/artifacts/", "files": []},
        "participants": participants
    }
    save_task_state(base_dir, task_id, state)
    return state


def load_task_state(base_dir: Path, task_id: str) -> Optional[Dict]:
    """Load existing task state."""
    state_file = get_task_state_file(base_dir, task_id)
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text())
    except json.JSONDecodeError:
        return None


def save_task_state(base_dir: Path, task_id: str, state: Dict):
    """Save task state atomically."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_file = get_task_state_file(base_dir, task_id)
    temp_file = state_file.with_suffix('.tmp')
    temp_file.write_text(json.dumps(state, indent=2))
    temp_file.rename(state_file)


def start_round(state: Dict, round_num: int, participants: List[str]) -> Dict:
    """Start new round in state."""
    now = datetime.now(timezone.utc).isoformat()
    round_state = {
        "round_number": round_num,
        "status": "running",
        "started_at": now,
        "completed_at": None,
        "participants": [
            {"agent": agent, "status": "pending", "started_at": None, "completed_at": None,
             "response_file": None, "parsed_response": None, "error": None}
            for agent in participants
        ],
        "consensus_check": {"all_responded": False, "consensus_reached": None, "decision": None, "blocking_issues": []}
    }
    state["rounds"].append(round_state)
    state["status"] = "running"
    return state


def start_participant(state: Dict, round_num: int, agent: str) -> Dict:
    """Mark participant as started."""
    round_state = state["rounds"][round_num - 1]
    for p in round_state["participants"]:
        if p["agent"] == agent:
            p["status"] = "running"
            p["started_at"] = datetime.now(timezone.utc).isoformat()
            break
    return state


def complete_participant(state: Dict, round_num: int, agent: str, response_file: str, parsed_response: Dict) -> Dict:
    """Mark participant as completed."""
    round_state = state["rounds"][round_num - 1]
    for p in round_state["participants"]:
        if p["agent"] == agent:
            p["status"] = "completed"
            p["completed_at"] = datetime.now(timezone.utc).isoformat()
            p["response_file"] = response_file
            p["parsed_response"] = parsed_response
            break
    if response_file not in state["artifacts"]["files"]:
        state["artifacts"]["files"].append(response_file)
    return state


def fail_participant(state: Dict, round_num: int, agent: str, error_type: str, error_message: str) -> Dict:
    """Mark participant as failed."""
    now = datetime.now(timezone.utc).isoformat()
    round_state = state["rounds"][round_num - 1]
    for p in round_state["participants"]:
        if p["agent"] == agent:
            p["status"] = "failed"
            p["completed_at"] = now
            p["error"] = {"type": error_type, "message": error_message, "timestamp": now}
            break
    state["failures"].append({
        "timestamp": now, "round_number": round_num, "agent": agent,
        "error_type": error_type, "error_message": error_message,
        "recoverable": error_type in ("timeout", "format_error")
    })
    return state


def complete_round(state: Dict, round_num: int, consensus: bool, blocking_issues: List[str],
                   actual_responded: int = None, expected_count: int = None) -> Dict:
    """Mark round as completed."""
    round_state = state["rounds"][round_num - 1]
    round_state["status"] = "completed"
    round_state["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Calculate all_responded based on actual vs expected counts
    if actual_responded is not None and expected_count is not None:
        all_responded = (actual_responded == expected_count)
    else:
        # Fallback: check participant statuses
        all_responded = all(p["status"] == "completed" for p in round_state["participants"])

    round_state["consensus_check"] = {
        "all_responded": all_responded, "actual_responded": actual_responded,
        "expected_count": expected_count, "consensus_reached": consensus,
        "decision": None, "blocking_issues": blocking_issues
    }
    if consensus:
        # Extract decision content from participant responses
        decisions = []
        for p in round_state["participants"]:
            if p["status"] == "completed" and p.get("parsed_response"):
                resp = p["parsed_response"]
                if isinstance(resp, dict) and resp.get("decision"):
                    decisions.append(f"{p['agent']}: {resp['decision']}")

        decision_text = "; ".join(decisions) if decisions else "Consensus reached"

        state["final_consensus"] = {
            "reached": True, "decision": decision_text,
            "blocking_issues": [], "round_number": round_num
        }
        state["status"] = "completed"
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
    return state


def get_pending_participants(state: Dict, round_num: int) -> List[str]:
    """Get list of pending participants in round."""
    if round_num > len(state["rounds"]):
        return []
    round_state = state["rounds"][round_num - 1]
    return [p["agent"] for p in round_state["participants"] if p["status"] == "pending"]
