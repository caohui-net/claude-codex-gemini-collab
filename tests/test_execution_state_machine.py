"""Tests for execution state machine transitions."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from execution_state_machine import ExecutionStateMachine, Phase


def test_valid_transition_planning_to_executing(tmp_path):
    """Test valid transition from PLANNING to EXECUTING."""
    state_machine = ExecutionStateMachine(tmp_path, "test-task-1")
    assert state_machine.state["phase"] == Phase.PLANNING.value

    state_machine.transition_to(Phase.EXECUTING)
    assert state_machine.state["phase"] == Phase.EXECUTING.value


def test_valid_transition_executing_to_completed(tmp_path):
    """Test valid transition from EXECUTING to COMPLETED."""
    state_machine = ExecutionStateMachine(tmp_path, "test-task-2")
    state_machine.transition_to(Phase.EXECUTING)

    state_machine.transition_to(Phase.COMPLETED)
    assert state_machine.state["phase"] == Phase.COMPLETED.value


def test_valid_transition_executing_to_failed(tmp_path):
    """Test valid transition from EXECUTING to FAILED."""
    state_machine = ExecutionStateMachine(tmp_path, "test-task-3")
    state_machine.transition_to(Phase.EXECUTING)

    state_machine.transition_to(Phase.FAILED)
    assert state_machine.state["phase"] == Phase.FAILED.value


def test_invalid_transition_planning_to_completed(tmp_path):
    """Test invalid transition from PLANNING to COMPLETED."""
    state_machine = ExecutionStateMachine(tmp_path, "test-task-4")

    with pytest.raises(ValueError, match="Invalid transition: planning → completed"):
        state_machine.transition_to(Phase.COMPLETED)


def test_invalid_transition_completed_to_executing(tmp_path):
    """Test invalid transition from COMPLETED to EXECUTING."""
    state_machine = ExecutionStateMachine(tmp_path, "test-task-5")
    state_machine.transition_to(Phase.EXECUTING)
    state_machine.transition_to(Phase.COMPLETED)

    with pytest.raises(ValueError, match="Invalid transition: completed → executing"):
        state_machine.transition_to(Phase.EXECUTING)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
