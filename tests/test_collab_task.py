import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collab_event import release_lock
from collab_init import init_collaboration
from collab_task import claim_task


def make_event(event_id, event_type, agent="claude", task_id="TASK-1", status=None, details=None):
    event = {
        "id": event_id,
        "type": event_type,
        "agent": agent,
        "timestamp": "2026-05-30T00:00:00+00:00",
        "summary": event_type,
    }
    if task_id is not None:
        event["task_id"] = task_id
    if status is not None:
        event["status"] = status
    if details is not None:
        event["details"] = details
    return event


class CollaborationTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)
        with contextlib.redirect_stdout(io.StringIO()):
            init_collaboration(self.base)

    def tearDown(self):
        self.tmpdir.cleanup()

    @property
    def collab_dir(self):
        return self.base / ".omc" / "collaboration"

    def write_events(self, events):
        (self.collab_dir / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events)
        )
        state = {
            "workflow_id": "test",
            "current_task": None,
            "active_agent": "none",
            "status": "initialized",
            "last_event_id": max((event["id"] for event in events), default=0),
            "updated_at": "2026-05-30T00:00:00+00:00",
        }
        (self.collab_dir / "state.json").write_text(json.dumps(state) + "\n")

    def claim(self, agent="codex"):
        with contextlib.redirect_stdout(io.StringIO()):
            return claim_task(self.base, "TASK-1", agent)

    def event_count(self):
        return len((self.collab_dir / "events.jsonl").read_text().splitlines())

    def lock_exists(self):
        return (self.collab_dir / "locks" / "journal.lock").exists()

    def test_open_task_can_be_claimed(self):
        self.write_events([make_event(1, "task_created", status="task_open")])

        self.assertEqual(self.claim(), 0)
        self.assertEqual(self.event_count(), 2)
        self.assertFalse(self.lock_exists())

    def test_same_agent_claim_is_idempotent(self):
        self.write_events([
            make_event(1, "task_created", status="task_open"),
            make_event(2, "task_claimed", agent="codex", status="in_progress"),
        ])

        self.assertEqual(self.claim(agent="codex"), 0)
        self.assertEqual(self.event_count(), 2)
        self.assertFalse(self.lock_exists())

    def test_all_protocol_active_statuses_block_other_agents(self):
        for status in ["claimed", "in_progress", "waiting", "blocked", "timeout_candidate"]:
            with self.subTest(status=status):
                self.write_events([
                    make_event(1, "task_created", status="task_open"),
                    make_event(2, "artifact_created", agent="claude", status=status),
                ])

                self.assertEqual(self.claim(), 1)
                self.assertEqual(self.event_count(), 2)
                self.assertFalse(self.lock_exists())

    def test_details_task_id_is_used_for_claim_state(self):
        self.write_events([
            make_event(1, "task_created", task_id=None, status="task_open", details={"task_id": "TASK-1"}),
            make_event(2, "handoff_requested", task_id=None, agent="gemini", details={"task_id": "TASK-1"}),
        ])

        self.assertEqual(self.claim(), 1)
        self.assertEqual(self.event_count(), 2)
        self.assertFalse(self.lock_exists())

    def test_completed_task_cannot_be_claimed(self):
        self.write_events([
            make_event(1, "task_created", status="task_open"),
            make_event(2, "completed", status="completed"),
        ])

        self.assertEqual(self.claim(), 1)
        self.assertEqual(self.event_count(), 2)
        self.assertFalse(self.lock_exists())

    def test_release_lock_owner_validation_keeps_lock_on_mismatch(self):
        lock_dir = self.collab_dir / "locks" / "journal.lock"
        lock_dir.mkdir(parents=True)
        (lock_dir / "owner.json").write_text(json.dumps({
            "agent": "claude",
            "task_id": "TASK-1",
        }))

        with self.assertRaises(ValueError):
            release_lock(self.collab_dir, agent="codex")
        self.assertTrue(lock_dir.exists())

        release_lock(self.collab_dir, agent="claude", task_id="TASK-1")
        self.assertFalse(lock_dir.exists())


if __name__ == "__main__":
    unittest.main()
