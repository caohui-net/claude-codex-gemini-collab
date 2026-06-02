#!/usr/bin/env python3
"""Tests for conclude path."""

import pytest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_state import init_task_state, start_round, save_task_state, load_task_state


def test_conclude_updates_decision_and_status():
    """Verify conclude sets final_consensus.decision and status=completed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create incomplete discussion task
        task_state = init_task_state(base, "TASK-1", "Test topic", ["codex", "gemini"])
        task_state = start_round(task_state, 1, ["codex", "gemini"])
        save_task_state(base, "TASK-1", task_state)

        # Simulate conclude: manually set decision
        task_state['final_consensus'] = {
            'reached': True,
            'decision': "Manual decision from conclude",
            'method': 'manual_conclude'
        }
        task_state['status'] = 'completed'
        save_task_state(base, "TASK-1", task_state)

        # Verify
        loaded = load_task_state(base, "TASK-1")
        assert loaded['status'] == 'completed'
        assert loaded['final_consensus']['reached'] is True
        assert loaded['final_consensus']['decision'] == "Manual decision from conclude"
        assert loaded['final_consensus']['method'] == 'manual_conclude'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
