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
    evidence_path = tmp_path / ".collab/tasks" / task_id / "evidence.json"
    assert evidence_path.exists()

    with open(evidence_path) as f:
        saved = json.load(f)
    assert saved["task_id"] == task_id


def test_verify_execution_with_changes():
    """Test verification succeeds when evidence complete."""
    evidence = {
        "task_id": "test",
        "timestamp": "2026-06-05T20:00:00Z",
        "file_count": 3,
        "changed_files": ["src/a.py", "src/b.py", "src/c.py"]
    }
    consensus = {"decision": "Test"}

    success, issues = verify_execution(evidence, consensus)

    assert success is True
    assert issues == []


def test_verify_execution_no_changes():
    """Test verification fails when no changes detected."""
    evidence = {
        "task_id": "test",
        "timestamp": "2026-06-05T20:00:00Z",
        "file_count": 0,
        "changed_files": []
    }
    consensus = {"decision": "Test"}

    success, issues = verify_execution(evidence, consensus)

    assert success is False
    assert "No file changes detected" in issues


def test_verify_execution_missing_fields():
    """Test verification fails when evidence incomplete."""
    evidence = {"file_count": 3}  # Missing required fields
    consensus = {"decision": "Test"}

    success, issues = verify_execution(evidence, consensus)

    assert success is False
    assert len(issues) > 0
    assert any("Missing evidence field" in issue for issue in issues)


def test_verify_execution_target_mismatch():
    """Test verification fails when expected targets not modified."""
    evidence = {
        "task_id": "test",
        "timestamp": "2026-06-05T20:00:00Z",
        "file_count": 2,
        "changed_files": ["other/x.py", "other/y.py"]
    }
    consensus = {
        "decision": "Test",
        "tasks": [{"target_file": "src/main.py"}]
    }

    success, issues = verify_execution(evidence, consensus)

    assert success is False
    assert any("Expected targets not modified" in issue for issue in issues)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
