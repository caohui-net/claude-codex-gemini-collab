#!/usr/bin/env python3
"""Audit workflow for three-party code review."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_event import append_event, read_events, read_state, write_state_atomically, acquire_lock, release_lock
from collab_paths import resolve_existing_base_dir, add_base_dir_arg


def trigger_audit(base_dir, task_id):
    """Trigger mandatory three-party audit."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    # Check if audit already running (idempotency)
    try:
        events = read_events(collab_dir / "events.jsonl")
        for event in reversed(events):
            if event.get("task_id") == task_id:
                if event.get("type") == "audit_started":
                    print(f"✓ Audit already running for {task_id}")
                    return 0
                if event.get("type") in ["audit_completed", "audit_failed"]:
                    print(f"ℹ️  Audit already completed for {task_id}")
                    return 0
    except Exception as e:
        print(f"❌ Error reading events: {e}")
        return 1

    # Create audit record
    audit_id = f"AUDIT-{task_id}"

    rc = append_event(
        base,
        event_type="audit_started",
        agent="claude",
        task_id=task_id,
        summary=f"Started three-party audit",
        details={
            "audit_id": audit_id,
            "required_agents": ["claude", "codex", "gemini"],
            "status": "pending",
        }
    )

    if rc != 0:
        print(f"❌ Failed to append audit_started event")
        return 1

    print(f"✓ Event appended: audit_started")
    print(f"✓ Audit ID: {audit_id}")
    print(f"📋 Required agents: claude, codex, gemini")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Trigger collaboration audit")
    add_base_dir_arg(parser)
    parser.add_argument("task_id", help="Task ID to audit")

    args = parser.parse_args()

    try:
        base_dir = resolve_existing_base_dir(args.base_dir)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    return trigger_audit(base_dir, args.task_id)


if __name__ == "__main__":
    sys.exit(main())
