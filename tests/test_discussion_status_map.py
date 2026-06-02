#!/usr/bin/env python3
"""Regression test for discussion_started/concluded STATUS_MAP bug fix."""

import json
import pytest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_event import append_event
from collab_state import rebuild_state, STATUS_MAP


def test_discussion_events_in_status_map():
    """Verify discussion_started and discussion_concluded are in STATUS_MAP."""
    assert "discussion_started" in STATUS_MAP
    assert "discussion_concluded" in STATUS_MAP
    assert STATUS_MAP["discussion_started"] == "discussion"
    assert STATUS_MAP["discussion_concluded"] == "discussion"


def test_discussion_events_ownership_neutral():
    """Verify discussion events don't corrupt active ownership."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        collab_dir = base / ".omc" / "collaboration"
        collab_dir.mkdir(parents=True)

        events_file = collab_dir / "events.jsonl"
        events_file.touch()

        state_file = collab_dir / "state.json"
        state_file.write_text(json.dumps({
            "last_event_id": 0,
            "status": "initialized",
            "current_task": None,
            "active_agent": None
        }))

        # Create active claim
        append_event(base, "task_created", "claude", "TASK-1", "Created task")
        append_event(base, "task_claimed", "codex", "TASK-1", "Claimed task")

        # Read events and rebuild state
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        state_after_claim = rebuild_state(events)
        assert state_after_claim["active_agent"] == "codex"
        assert state_after_claim["current_task"] == "TASK-1"
        assert state_after_claim["status"] == "in_progress"

        # Append discussion_started (ownership-neutral)
        append_event(base, "discussion_started", "system", "DISCUSS-1", "Discussion started")

        # Verify event has correct status
        with open(events_file) as f:
            events = [json.loads(line) for line in f if line.strip()]

        discussion_started_event = events[-1]
        assert discussion_started_event["type"] == "discussion_started"

        # Rebuild state - ownership should remain unchanged
        state_after_started = rebuild_state(events)
        assert state_after_started["active_agent"] == "codex"
        assert state_after_started["current_task"] == "TASK-1"

        # Append discussion_concluded (ownership-neutral)
        append_event(base, "discussion_concluded", "system", "DISCUSS-1", "Discussion concluded")

        with open(events_file) as f:
            events = [json.loads(line) for line in f if line.strip()]

        # Rebuild state - ownership should still remain unchanged
        state_after_concluded = rebuild_state(events)
        assert state_after_concluded["active_agent"] == "codex"
        assert state_after_concluded["current_task"] == "TASK-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
