#!/usr/bin/env python3
"""Classify and route collaboration tasks."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from task_classifier import classify_task, route_to_agents
from collab_event import append_event, read_events, read_state
from collab_paths import resolve_existing_base_dir, add_base_dir_arg


def classify_and_route(base_dir, task_id):
    """Classify task and determine routing."""
    base = Path(base_dir).resolve()
    collab_dir = base / ".collab"

    # Read task description from events
    events = read_events(collab_dir / "events.jsonl")
    task_event = None
    for event in events:
        if event.get("type") == "task_created" and event.get("task_id") == task_id:
            task_event = event
            break

    if not task_event:
        print(f"❌ Task {task_id} not found")
        return 1

    description = task_event.get("summary", "").replace("Created task: ", "")

    # Classify
    result = classify_task(description)
    agents = route_to_agents(result)

    # Output results
    print(f"✓ Task classified: {task_id}")
    print(f"  Type: {result.task_type}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Risk: {result.risk_level}")
    print(f"  Routed to: {', '.join(agents)}")
    print(f"  Capabilities: {', '.join(result.required_capabilities)}")

    # Append classification event (分类结果，保留assigned_agents兼容性)
    classification_data = {
        "task_type": result.task_type,
        "confidence": result.confidence,
        "risk_level": result.risk_level,
        "matched_rules": result.matched_rules,
        "required_capabilities": result.required_capabilities,
        "assigned_agents": agents,  # 保留以兼容旧override explain
    }

    classify_rc = append_event(
        base,
        event_type="classify_requested",
        agent="claude",
        task_id=task_id,
        summary=f"Classified task as {result.task_type}",
        details=classification_data
    )

    if classify_rc != 0:
        print(f"❌ Failed to append classify_requested event")
        return 1

    print(f"✓ Event appended: classify_requested")

    # Append routing decision event (路由决策)
    routing_data = {
        "assigned_agents": agents,
        "task_type": result.task_type,
        "confidence": result.confidence,
        "required_capabilities": result.required_capabilities,
        "route_reason": f"Auto-routed based on {result.task_type} classification",
        "classifier_version": "1.0",
    }

    route_rc = append_event(
        base,
        event_type="route_decided",
        agent="claude",
        task_id=task_id,
        summary=f"Routed to {', '.join(agents)}",
        details=routing_data
    )

    if route_rc != 0:
        print(f"❌ Failed to append route_decided event")
        return 1

    print(f"✓ Event appended: route_decided")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Classify collaboration tasks")
    add_base_dir_arg(parser)
    parser.add_argument("task_id", help="Task ID to classify")

    args = parser.parse_args()

    try:
        base_dir = resolve_existing_base_dir(args.base_dir)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    return classify_and_route(base_dir, args.task_id)


if __name__ == "__main__":
    sys.exit(main())
