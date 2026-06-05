"""Tests for consensus contract generation."""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import save_consensus_contract


def test_save_consensus_when_reached(tmp_path):
    """Test consensus.json is saved when consensus reached."""
    task_id = "test-task-123"
    task_state = {
        'final_consensus': {
            'reached': True,
            'decision': 'Test decision text',
            'round': 3
        }
    }

    save_consensus_contract(tmp_path, task_id, task_state)

    consensus_path = tmp_path / ".omc/collaboration/tasks" / task_id / "consensus.json"
    assert consensus_path.exists(), "consensus.json should be created"

    with open(consensus_path) as f:
        consensus = json.load(f)

    assert consensus['task_id'] == task_id
    assert consensus['decision'] == 'Test decision text'
    assert consensus['round'] == 3
    assert 'achieved_at' in consensus
    assert isinstance(consensus['tasks'], list)
    assert isinstance(consensus['blocking_issues'], list)


def test_no_save_when_not_reached(tmp_path):
    """Test consensus.json is not saved when consensus not reached."""
    task_id = "test-task-456"
    task_state = {
        'final_consensus': {
            'reached': False,
            'reason': 'timeout'
        }
    }

    save_consensus_contract(tmp_path, task_id, task_state)

    consensus_path = tmp_path / ".omc/collaboration/tasks" / task_id / "consensus.json"
    assert not consensus_path.exists(), "consensus.json should not be created when consensus not reached"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
