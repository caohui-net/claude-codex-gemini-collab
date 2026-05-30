import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collab_event import append_event, release_lock
from collab_init import init_collaboration
from collab_task import claim_task
from collab_validate import validate


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

    def test_append_event_rejects_malformed_event_log_without_writing(self):
        events_file = self.collab_dir / "events.jsonl"
        events_file.write_text("{not json}\n")
        before = events_file.read_text()

        with contextlib.redirect_stdout(io.StringIO()):
            result = append_event(self.base, "completed", "codex", "TASK-1", "done")

        self.assertEqual(result, 1)
        self.assertEqual(events_file.read_text(), before)
        self.assertFalse(self.lock_exists())

    def test_append_event_rejects_duplicate_ids_without_writing(self):
        events = [
            make_event(1, "task_created", status="task_open"),
            make_event(1, "artifact_created", status="in_progress"),
        ]
        self.write_events(events)
        events_file = self.collab_dir / "events.jsonl"
        before = events_file.read_text()

        with contextlib.redirect_stdout(io.StringIO()):
            result = append_event(self.base, "completed", "codex", "TASK-1", "done")

        self.assertEqual(result, 1)
        self.assertEqual(events_file.read_text(), before)
        self.assertFalse(self.lock_exists())

    def test_append_event_rejects_missing_state_without_writing(self):
        self.write_events([make_event(1, "task_created", status="task_open")])
        (self.collab_dir / "state.json").unlink()
        events_file = self.collab_dir / "events.jsonl"
        before = events_file.read_text()

        with contextlib.redirect_stdout(io.StringIO()):
            result = append_event(self.base, "completed", "codex", "TASK-1", "done")

        self.assertEqual(result, 1)
        self.assertEqual(events_file.read_text(), before)
        self.assertFalse(self.lock_exists())

    def test_validate_missing_state_fails_gracefully(self):
        (self.collab_dir / "state.json").unlink()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = validate(self.base)

        self.assertEqual(result, 1)
        self.assertIn("state.json missing", output.getvalue())

    def test_validate_initialized_empty_events_passes(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = validate(self.base)

        self.assertEqual(result, 0)
        self.assertIn("0 events valid", output.getvalue())

    def test_validate_empty_events_with_valid_state_fails_gracefully(self):
        (self.collab_dir / "events.jsonl").write_text("")
        state = {
            "workflow_id": "test",
            "current_task": None,
            "active_agent": "none",
            "status": "in_progress",
            "last_event_id": 1,
            "updated_at": "2026-05-30T00:00:00+00:00",
        }
        (self.collab_dir / "state.json").write_text(json.dumps(state) + "\n")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = validate(self.base)

        self.assertEqual(result, 1)
        self.assertIn("Event ID mismatch: state=1, log max=0", output.getvalue())

    def test_repair_handles_scalar_events_gracefully(self):
        from collab_validate import repair

        # Write events.jsonl with scalar and valid events
        events_file = self.collab_dir / "events.jsonl"
        events_file.write_text('123\n{"id": 1, "type": "test", "status": "ok"}\n"string"\n')

        # Write valid state.json
        state_file = self.collab_dir / "state.json"
        state_file.write_text('{"last_event_id": 0}')

        # Run repair - should not crash
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = repair(self.base)

        self.assertEqual(result, 0)
        self.assertIn("Rebuilt state.json from 1 events", output.getvalue())

        # Verify state was rebuilt correctly (only valid event counted)
        state = json.loads(state_file.read_text())
        self.assertEqual(state["last_event_id"], 1)

    def test_handoff_validates_task_exists(self):
        self.write_events([make_event(1, "task_created", task_id="TASK-1", status="task_open")])
        events_file = self.collab_dir / "events.jsonl"
        before = events_file.read_text()

        # Try handoff for non-existent task
        with contextlib.redirect_stdout(io.StringIO()):
            result = append_event(self.base, "handoff_requested", "claude", "TASK-999", "handoff to codex")

        self.assertEqual(result, 1)
        self.assertEqual(events_file.read_text(), before)
        self.assertFalse(self.lock_exists())

    def test_handoff_rejects_ghost_task(self):
        # Ghost task: artifact_created mentions task_id but no task_created event
        self.write_events([make_event(1, "artifact_created", task_id="TASK-GHOST", status="in_progress")])
        events_file = self.collab_dir / "events.jsonl"
        before = events_file.read_text()

        # Try handoff for ghost task
        with contextlib.redirect_stdout(io.StringIO()):
            result = append_event(self.base, "handoff_requested", "claude", "TASK-GHOST", "handoff to codex")

        self.assertEqual(result, 1)
        self.assertEqual(events_file.read_text(), before)
        self.assertFalse(self.lock_exists())

    def test_create_task_fails_on_malformed_events(self):
        from collab_task import create_task

        # Corrupt events.jsonl
        events_file = self.collab_dir / "events.jsonl"
        events_file.write_text("{bad json}\n")

        # Try to create task
        with contextlib.redirect_stdout(io.StringIO()):
            result = create_task(self.base, "test task")

        # Should fail and not create orphan task file
        self.assertEqual(result, 1)
        task_files = list((self.collab_dir / "tasks").glob("*.md"))
        self.assertEqual(len(task_files), 0)

    def test_cli_smoke_init_create_claim_complete_validate(self):
        with tempfile.TemporaryDirectory() as smoke_dir:
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

            def run_script(*args):
                return subprocess.run(
                    [sys.executable, *args],
                    cwd=smoke_dir,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )

            init_result = run_script(str(ROOT / "scripts" / "collab_init.py"))
            self.assertEqual(init_result.returncode, 0, init_result.stderr)

            create_result = run_script(
                str(ROOT / "scripts" / "collab_task.py"),
                "create",
                "Smoke test task",
            )
            self.assertEqual(create_result.returncode, 0, create_result.stderr)

            smoke_collab_dir = Path(smoke_dir) / ".omc" / "collaboration"
            events = [
                json.loads(line)
                for line in (smoke_collab_dir / "events.jsonl").read_text().splitlines()
            ]
            task_id = events[-1]["task_id"]

            claim_result = run_script(
                str(ROOT / "scripts" / "collab_task.py"),
                "claim",
                task_id,
                "codex",
            )
            self.assertEqual(claim_result.returncode, 0, claim_result.stderr)

            complete_result = run_script(
                str(ROOT / "scripts" / "collab_task.py"),
                "complete",
                task_id,
                "codex",
            )
            self.assertEqual(complete_result.returncode, 0, complete_result.stderr)

            validate_result = run_script(str(ROOT / "scripts" / "collab_validate.py"))
            self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)


if __name__ == "__main__":
    unittest.main()
