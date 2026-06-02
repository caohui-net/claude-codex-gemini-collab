#!/usr/bin/env python3
"""Tests for ccg_collab.event.io module."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.event.io import read_events, read_state, write_state_atomically


def test_read_events():
    """Test read_events validates and parses events.jsonl."""
    with tempfile.TemporaryDirectory() as tmpdir:
        events_file = Path(tmpdir) / "events.jsonl"
        events_file.write_text('{"id": 1, "type": "test"}\n{"id": 2, "type": "test2"}\n')

        events = read_events(events_file)
        assert len(events) == 2
        assert events[0]["id"] == 1
        assert events[1]["id"] == 2
        print("✓ read_events parses valid events")


def test_read_state():
    """Test read_state validates and parses state.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        state_file.write_text('{"last_event_id": 5, "status": "test"}')

        state = read_state(state_file)
        assert state["last_event_id"] == 5
        assert state["status"] == "test"
        print("✓ read_state parses valid state")


def test_write_state_atomically():
    """Test write_state_atomically creates valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        test_state = {"last_event_id": 10, "status": "completed"}

        write_state_atomically(state_file, test_state)

        assert state_file.exists()
        written = json.loads(state_file.read_text())
        assert written["last_event_id"] == 10
        print("✓ write_state_atomically creates valid file")


if __name__ == "__main__":
    print("=== ccg_collab.event.io Tests ===\n")

    failed = 0
    tests = [test_read_events, test_read_state, test_write_state_atomically]

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(0 if failed == 0 else 1)
