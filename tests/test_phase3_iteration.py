"""Tests for Phase 3.3 automated iteration loop."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_execute import generate_iteration_topic, check_termination


def test_generate_iteration_topic():
    """Test iteration topic generation from feedback."""
    feedback_items = ["Missing field X", "Invalid value Y", "No changes detected"]
    topic = generate_iteration_topic("TASK-123", feedback_items, 1)

    assert "[Iteration 1]" in topic
    assert "TASK-123" in topic
    assert "Missing field X" in topic
    assert "Invalid value Y" in topic
    assert "No changes detected" in topic


def test_generate_iteration_topic_truncation():
    """Test topic truncation when more than 3 issues."""
    feedback_items = ["Issue 1", "Issue 2", "Issue 3", "Issue 4", "Issue 5"]
    topic = generate_iteration_topic("TASK-456", feedback_items, 2)

    assert "[Iteration 2]" in topic
    assert "Issue 1" in topic
    assert "Issue 2" in topic
    assert "Issue 3" in topic
    assert "+2 more" in topic


def test_check_termination_max_iterations(tmp_path):
    """Test termination when max iterations reached."""
    should_terminate, reason = check_termination(tmp_path, "TASK-123", 4, 3)

    assert should_terminate is True
    assert "Maximum iterations" in reason
    assert "3" in reason


def test_check_termination_missing_consensus(tmp_path):
    """Test termination when consensus missing."""
    task_id = "TASK-789"
    should_terminate, reason = check_termination(tmp_path, task_id, 1, 3)

    assert should_terminate is True
    assert "No consensus found" in reason


def test_check_termination_continue(tmp_path):
    """Test iteration continues when under limit and consensus exists."""
    task_id = "TASK-456"
    task_dir = tmp_path / ".collab/tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create required artifacts
    (task_dir / "consensus.json").write_text('{"decision": "test"}')
    (task_dir / "review_report.json").write_text('{"status": "rejected"}')
    (task_dir / "evidence.json").write_text('{"task_id": "test"}')

    should_terminate, reason = check_termination(tmp_path, task_id, 2, 3)

    assert should_terminate is False
    assert reason == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
