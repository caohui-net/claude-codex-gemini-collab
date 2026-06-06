"""Tests for execution logic."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_execution_with_tasks(tmp_path):
    """Test execution creates files from consensus tasks."""
    # Initialize git repo for audit/verification
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create consensus.json with tasks
    task_id = "test-exec-1"
    consensus_dir = tmp_path / ".omc/collaboration/tasks" / task_id
    consensus_dir.mkdir(parents=True)

    consensus = {
        "task_id": task_id,
        "decision": "Create test files",
        "tasks": [
            {"target_file": "src/test1.py", "content": "# Test 1\n", "action": "write"},
            {"target_file": "src/test2.py", "content": "# Test 2\n", "action": "write"}
        ]
    }

    (consensus_dir / "consensus.json").write_text(json.dumps(consensus))

    # Initial commit so there's a HEAD
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    # Run execution
    from collab_execute import main
    import sys
    old_argv = sys.argv
    sys.argv = ["collab_execute.py", task_id, "--base-dir", str(tmp_path), "--skip-approval"]

    try:
        result = main()
    finally:
        sys.argv = old_argv

    # Verify files created
    assert (tmp_path / "src/test1.py").exists()
    assert (tmp_path / "src/test1.py").read_text() == "# Test 1\n"
    assert (tmp_path / "src/test2.py").exists()
    assert result == 0


def test_execution_no_tasks(tmp_path):
    """Test execution with empty tasks list."""
    # Initialize git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    task_id = "test-exec-2"
    consensus_dir = tmp_path / ".omc/collaboration/tasks" / task_id
    consensus_dir.mkdir(parents=True)

    consensus = {"task_id": task_id, "decision": "No tasks", "tasks": []}
    (consensus_dir / "consensus.json").write_text(json.dumps(consensus))

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, capture_output=True)

    from collab_execute import main
    import sys
    old_argv = sys.argv
    sys.argv = ["collab_execute.py", task_id, "--base-dir", str(tmp_path), "--skip-approval"]

    try:
        result = main()
    finally:
        sys.argv = old_argv

    # Should complete successfully even with no tasks
    assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
