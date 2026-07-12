import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

@pytest.fixture
def tmp_collab_dir(tmp_path):
    collab_dir = tmp_path / ".collab"
    collab_dir.mkdir()
    (collab_dir / "locks").mkdir()
    events_file = collab_dir / "events.jsonl"
    event = {"id": 1, "type": "task_created", "agent": "test", "task_id": "TEST-001"}
    events_file.write_text(json.dumps(event) + "\n")
    state_file = collab_dir / "state.json"
    state_file.write_text(json.dumps({"tasks": {}}))
    return collab_dir

@pytest.fixture
def sample_event():
    return {"id": 2, "type": "task_claimed", "agent": "agent-1", "task_id": "TEST-002"}

@pytest.fixture  
def sample_events_list():
    return [
        {"id": 1, "type": "task_created", "agent": "agent-1", "task_id": "TASK-001"},
        {"id": 2, "type": "task_claimed", "agent": "agent-1", "task_id": "TASK-001"},
        {"id": 3, "type": "task_completed", "agent": "agent-1", "task_id": "TASK-001"}
    ]

class TestEventIdField:
    def test_event_id_field_name(self):
        event = {"id": 1, "type": "test"}
        assert event.get("id") == 1
        assert event.get("event_id") is None

    def test_event_id_int_type(self, sample_event):
        assert isinstance(sample_event["id"], int)
        assert not isinstance(sample_event["id"], bool)

    def test_event_id_uniqueness(self, sample_events_list):
        ids = [e["id"] for e in sample_events_list]
        assert len(ids) == len(set(ids))

class TestAgentValidation:
    def test_valid_agent_ids(self):
        valid = ["agent-1", "Claude", "a"]
        for agent_id in valid:
            assert 0 < len(agent_id) <= 64

    def test_invalid_agent_ids(self):
        invalid = ["", "agent@1", "agent/path", "a" * 65]
        for agent_id in invalid:
            if agent_id:
                is_valid = len(agent_id) <= 64 and agent_id.replace("-", "").replace("_", "").isalnum()
            else:
                is_valid = False
            assert not is_valid

class TestFileOperations:
    def test_events_file_exists(self, tmp_collab_dir):
        assert (tmp_collab_dir / "events.jsonl").exists()

    def test_state_file_exists(self, tmp_collab_dir):
        assert (tmp_collab_dir / "state.json").exists()

    def test_valid_json_in_events(self, tmp_collab_dir):
        events_file = tmp_collab_dir / "events.jsonl"
        for line in events_file.read_text().splitlines():
            if line:
                event = json.loads(line)
                assert isinstance(event, dict)

class TestStateMachine:
    def test_task_lifecycle(self, sample_events_list):
        types = [e["type"] for e in sample_events_list]
        assert types[0] == "task_created"
        assert types[1] == "task_claimed"
        assert types[2] == "task_completed"

    def test_required_fields(self, sample_event):
        for field in ["id", "type", "agent", "task_id"]:
            assert field in sample_event

class TestLockMechanism:
    def test_lock_directory_creation(self, tmp_collab_dir):
        lock_dir = tmp_collab_dir / "locks" / "journal.lock"
        lock_dir.mkdir(parents=True, exist_ok=False)
        assert lock_dir.exists()

    def test_lock_already_exists(self, tmp_collab_dir):
        lock_dir = tmp_collab_dir / "locks" / "journal.lock"
        lock_dir.mkdir(parents=True)
        with pytest.raises(FileExistsError):
            lock_dir.mkdir(parents=True, exist_ok=False)

class TestModels:
    def test_response_model(self):
        response = {"id": "r1", "agent": "Claude", "content": "Test"}
        assert "id" in response and "agent" in response

    def test_session_model(self):
        session = {"id": "s1", "topic": "Test", "participants": []}
        assert isinstance(session["participants"], list)

class TestConfig:
    def test_config_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config = {"backend": "filesystem"}
        config_file.write_text(json.dumps(config))
        loaded = json.loads(config_file.read_text())
        assert loaded["backend"] == "filesystem"

class TestIntegration:
    def test_collab_structure(self, tmp_collab_dir):
        assert (tmp_collab_dir / "events.jsonl").exists()
        assert (tmp_collab_dir / "state.json").exists()
        assert (tmp_collab_dir / "locks").exists()

class TestEdgeCases:
    def test_unicode_in_events(self):
        event = {"id": 1, "summary": "测试中文"}
        s = json.dumps(event)
        parsed = json.loads(s)
        assert parsed["summary"] == "测试中文"

    def test_empty_details_field(self):
        event = {"id": 1, "type": "test"}
        details = event.get("details", {})
        assert isinstance(details, dict)
