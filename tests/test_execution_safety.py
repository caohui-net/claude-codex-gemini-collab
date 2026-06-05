"""Tests for execution safety mechanisms."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_execute import require_approval, create_snapshot, audit_execution


def test_require_approval_yes():
    """Test approval with 'yes' response."""
    consensus = {"decision": "Test decision", "tasks": []}

    with patch('builtins.input', return_value='yes'):
        result = require_approval(consensus)

    assert result is True


def test_require_approval_no():
    """Test approval with 'no' response."""
    consensus = {"decision": "Test decision", "tasks": []}

    with patch('builtins.input', return_value='no'):
        result = require_approval(consensus)

    assert result is False


@patch('subprocess.run')
def test_create_snapshot_success(mock_run, tmp_path):
    """Test snapshot creation in git repo."""
    mock_run.return_value = MagicMock(
        stdout="abc123def456\n",
        returncode=0
    )

    snapshot = create_snapshot(tmp_path)

    assert snapshot == "abc123def456"
    mock_run.assert_called_once()


@patch('subprocess.run')
def test_create_snapshot_no_git(mock_run, tmp_path):
    """Test snapshot when no git repo exists."""
    import subprocess
    mock_run.side_effect = subprocess.CalledProcessError(128, 'git')

    snapshot = create_snapshot(tmp_path)

    assert snapshot == ""


@patch('subprocess.run')
def test_audit_execution_with_changes(mock_run, tmp_path):
    """Test audit with file changes."""
    mock_run.return_value = MagicMock(
        stdout="file1.py\nfile2.py\n",
        returncode=0
    )

    changed = audit_execution(tmp_path, "abc123")

    assert len(changed) == 2
    assert "file1.py" in changed
    assert "file2.py" in changed


@patch('subprocess.run')
def test_audit_execution_no_changes(mock_run, tmp_path):
    """Test audit with no changes."""
    mock_run.return_value = MagicMock(
        stdout="",
        returncode=0
    )

    changed = audit_execution(tmp_path, "abc123")

    assert changed == []


def test_audit_execution_no_snapshot(tmp_path):
    """Test audit when no snapshot exists."""
    changed = audit_execution(tmp_path, "")

    assert changed == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
