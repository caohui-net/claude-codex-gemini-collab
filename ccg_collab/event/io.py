"""Event and state I/O utilities."""

import json
from pathlib import Path
from typing import List, Dict


def read_events(events_file: Path) -> List[Dict]:
    """Read and validate events.jsonl."""
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


def read_state(state_file: Path) -> Dict:
    """Read and validate state.json."""
    if not state_file.exists():
        raise ValueError("state.json missing")

    try:
        state = json.loads(state_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"state.json malformed: {e}") from e

    if not isinstance(state, dict):
        raise ValueError("state.json must be a JSON object")

    return state


def write_state_atomically(state_file: Path, state: Dict, agent: str = "system") -> None:
    """Write state through validated temp file and atomic rename."""
    temp_file = state_file.with_suffix(f'.tmp.{agent}')
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
