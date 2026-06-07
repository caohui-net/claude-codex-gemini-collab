#!/usr/bin/env python3
"""Manual routing override for collaboration tasks."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from collab_event import append_event, read_events
from collab_paths import resolve_existing_base_dir, add_base_dir_arg


def override_routing(base_dir, task_id, agent, reason):
    """Override automatic routing decision."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    events = read_events(collab_dir / "events.jsonl")
    next_id = max((e.get('id', 0) for e in events), default=0) + 1

    event = {
        "id": next_id,
        "type": "manual_override",
        "agent": "claude",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "summary": f"Manual override: assign to {agent}",
        "details": {
            "assigned_agent": agent,
            "reason": reason,
            "override_by": "claude"
        }
    }

    with (collab_dir / "events.jsonl").open('a') as f:
        f.write(json.dumps(event) + '\n')

    print(f"✓ Event {next_id} appended: manual_override")
    print(f"✓ Task {task_id} reassigned to {agent}")
    print(f"📝 Reason: {reason}")
    return 0


def explain_routing(base_dir, task_id):
    """Show routing decision explanation."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".omc" / "collaboration"

    events = read_events(collab_dir / "events.jsonl")

    for event in reversed(events):
        if event.get("task_id") == task_id:
            if event.get("type") == "classify_requested":
                details = event.get("details", {})
                print(f"📋 Task: {task_id}")
                print(f"  Type: {details.get('task_type', 'unknown')}")
                print(f"  Confidence: {details.get('confidence', 0):.2f}")
                print(f"  Agents: {', '.join(details.get('assigned_agents', []))}")
                print(f"  Risk: {details.get('risk_level', 'unknown')}")
                return 0

    print(f"ℹ️  No classification found for {task_id}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Manual routing control")
    add_base_dir_arg(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Override command
    override_parser = subparsers.add_parser("override", help="Override routing")
    override_parser.add_argument("task_id", help="Task ID")
    override_parser.add_argument("--assign", required=True, help="Agent to assign")
    override_parser.add_argument("--reason", required=True, help="Override reason")

    # Explain command
    explain_parser = subparsers.add_parser("explain", help="Explain routing")
    explain_parser.add_argument("task_id", help="Task ID")

    args = parser.parse_args()

    try:
        base_dir = resolve_existing_base_dir(args.base_dir)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    if args.command == "override":
        return override_routing(base_dir, args.task_id, args.assign, args.reason)
    elif args.command == "explain":
        return explain_routing(base_dir, args.task_id)


if __name__ == "__main__":
    sys.exit(main())
