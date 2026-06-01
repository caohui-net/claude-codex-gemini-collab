#!/usr/bin/env python3
"""Regression tests for handoff rejection bug fixes."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collab_event import append_event, get_active_owner, read_events
from collab_init import init_collaboration


class HandoffRejectionTests(unittest.TestCase):
    """Test handoff rejection returns ownership to requester."""

    def test_handoff_rejected_returns_to_requester(self):
        """After handoff_rejected, owner should be requester, not rejecter."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            init_collaboration(tmp_dir)

            # Claude creates and claims task
            append_event(tmp_dir, "task_created", "claude", "TASK-1", "test task")
            append_event(tmp_dir, "task_claimed", "claude", "TASK-1", "claimed")

            # Claude requests handoff to codex
            append_event(tmp_dir, "handoff_requested", "claude", "TASK-1", "handoff to codex",
                        details={"target_agent": "codex"})

            # Codex rejects handoff
            append_event(tmp_dir, "handoff_rejected", "codex", "TASK-1", "rejected")

            # Owner should be claude (requester), not codex (rejecter)
            events_file = tmp_dir / ".omc" / "collaboration" / "events.jsonl"
            events = read_events(events_file)
            owner = get_active_owner(events, "TASK-1")

            self.assertEqual(owner, "claude",
                           "After rejection, owner should return to requester (claude), not rejecter (codex)")

    def test_handoff_cancelled_returns_to_requester(self):
        """After handoff_cancelled, owner should be requester."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            init_collaboration(tmp_dir)

            append_event(tmp_dir, "task_created", "claude", "TASK-1", "test task")
            append_event(tmp_dir, "task_claimed", "claude", "TASK-1", "claimed")
            append_event(tmp_dir, "handoff_requested", "claude", "TASK-1", "handoff to codex",
                        details={"target_agent": "codex"})
            append_event(tmp_dir, "handoff_cancelled", "claude", "TASK-1", "cancelled")

            events_file = tmp_dir / ".omc" / "collaboration" / "events.jsonl"
            events = read_events(events_file)
            owner = get_active_owner(events, "TASK-1")

            self.assertEqual(owner, "claude")

    def test_handoff_requested_requires_target_agent(self):
        """handoff_requested must have target_agent in details."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            init_collaboration(tmp_dir)

            append_event(tmp_dir, "task_created", "claude", "TASK-1", "test task")
            append_event(tmp_dir, "task_claimed", "claude", "TASK-1", "claimed")

            # Try handoff without target_agent - should fail
            result = append_event(tmp_dir, "handoff_requested", "claude", "TASK-1",
                                "handoff without target", details={})

            self.assertEqual(result, 1, "handoff_requested without target_agent should fail")


if __name__ == "__main__":
    unittest.main()
