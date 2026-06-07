"""Execution state machine for collaboration."""

from pathlib import Path
import json
from datetime import datetime
from enum import Enum


class Phase(Enum):
    """Execution phases."""
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionStateMachine:
    """Minimal state machine for execution tracking."""

    # Valid phase transitions
    TRANSITIONS = {
        Phase.PLANNING: [Phase.EXECUTING, Phase.FAILED],
        Phase.EXECUTING: [Phase.VERIFYING, Phase.FAILED],
        Phase.VERIFYING: [Phase.COMPLETED, Phase.FAILED],
        Phase.COMPLETED: [],
        Phase.FAILED: []
    }

    def __init__(self, base_dir: Path, task_id: str):
        self.base_dir = base_dir
        self.task_id = task_id
        self.state_path = base_dir / ".omc/collaboration/tasks" / task_id / "execution_state.json"
        self.state = self.load_state()

    def load_state(self) -> dict:
        """Load or initialize state."""
        if self.state_path.exists():
            with open(self.state_path) as f:
                return json.load(f)

        return {
            "task_id": self.task_id,
            "phase": Phase.PLANNING.value,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }

    def save_state(self):
        """Persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def transition_to(self, phase: Phase):
        """Transition to new phase with validation."""
        current_phase = Phase(self.state["phase"])

        # Validate transition
        if phase not in self.TRANSITIONS[current_phase]:
            raise ValueError(f"Invalid transition: {current_phase.value} → {phase.value}")

        old_phase = self.state["phase"]
        self.state["phase"] = phase.value
        self.state["updated_at"] = datetime.now().isoformat()
        self.save_state()
        print(f"🔄 {old_phase} → {phase.value}")
