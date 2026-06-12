"""Tests for path validation integration in collab_execute."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_execute import validate_target_files, validate_changed_files


def test_validate_target_files_empty_tasks(tmp_path):
    """Test target validation with empty tasks list."""
    consensus = {"tasks": []}

    valid, violations = validate_target_files(consensus, tmp_path)

    assert valid is True
    assert violations == []


def test_validate_target_files_allowed_path(tmp_path):
    """Test target validation with allowed path."""
    consensus = {"tasks": [{"target_file": "src/test.py"}]}
    (tmp_path / "src").mkdir()

    valid, violations = validate_target_files(consensus, tmp_path)

    assert valid is True
    assert violations == []


def test_validate_target_files_forbidden_path(tmp_path):
    """Test target validation with forbidden path."""
    consensus = {"tasks": [{"target_file": ".git/config"}]}

    valid, violations = validate_target_files(consensus, tmp_path)

    assert valid is False
    assert len(violations) == 1
    assert ".git/config" in violations[0]


def test_validate_changed_files_empty_list(tmp_path):
    """Test changed file validation with empty list."""
    valid, violations = validate_changed_files([], tmp_path)

    assert valid is True
    assert violations == []


def test_validate_changed_files_allowed(tmp_path):
    """Test changed file validation with allowed paths."""
    (tmp_path / "src").mkdir()

    valid, violations = validate_changed_files(["src/a.py", "src/b.py"], tmp_path)

    assert valid is True
    assert violations == []


def test_validate_changed_files_forbidden(tmp_path):
    """Test changed file validation with forbidden path."""
    valid, violations = validate_changed_files([".collab/state.json"], tmp_path)

    assert valid is False
    assert len(violations) == 1
    assert "state.json" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
