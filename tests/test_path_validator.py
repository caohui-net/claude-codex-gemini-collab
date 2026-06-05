"""Tests for path_validator."""

import sys
from pathlib import Path
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from path_validator import validate_path, EXECUTION_POLICY


def test_allowed_path(tmp_path):
    """Test path in allowed list passes validation."""
    # Create test structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    test_file = src_dir / "test.py"
    test_file.touch()

    valid, error = validate_path("src/test.py", tmp_path)
    assert valid, f"Expected valid path, got error: {error}"


def test_forbidden_path(tmp_path):
    """Test path in forbidden list fails validation."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    valid, error = validate_path(".git/config", tmp_path)
    assert not valid
    assert "Forbidden" in error


def test_absolute_path_rejected(tmp_path):
    """Test absolute paths are rejected by default."""
    valid, error = validate_path("/etc/passwd", tmp_path)
    assert not valid
    assert "Absolute" in error


def test_outside_workspace_rejected(tmp_path):
    """Test paths outside workspace are rejected."""
    valid, error = validate_path("../../../etc/passwd", tmp_path)
    assert not valid
    assert "outside workspace" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
