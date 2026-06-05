"""Tests for execution verification logic."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_execute import collect_evidence, verify_execution


def test_collect_evidence(tmp_path):
    """Test evidence collection creates evidence.json."""
    task_id = "test-task-123"
    changed_files = ["file1.py", "file2.py"]

    evidence = collect_evidence(tmp_path, task_id, changed_files)

    assert evidence["task_id"] == task_id
    assert evidence["changed_files"] == changed_files
    assert evidence["file_count"] == 2
    assert "timestamp" in evidence

    # Verify evidence file created
    evidence_path = tmp_path / ".omc/collaboration/tasks" / task_id / "evidence.json"
    assert evidence_path.exists()

    with open(evidence_path) as f:
        saved = json.load(f)
    assert saved["task_id"] == task_id


def test_verify_execution_with_changes():
    """Test verification succeeds when files changed."""
    evidence = {"file_count": 3, "changed_files": ["a.py", "b.py", "c.py"]}
    consensus = {"decision": "Test"}

    success = verify_execution(evidence, consensus)

    assert success is True


def test_verify_execution_no_changes():
    """Test verification fails when no changes detected."""
    evidence = {"file_count": 0, "changed_files": []}
    consensus = {"decision": "Test"}

    success = verify_execution(evidence, consensus)

    assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
