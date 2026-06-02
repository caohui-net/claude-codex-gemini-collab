#!/usr/bin/env python3
"""Tests for ccg_collab.core.paths module."""

import os
import sys
import tempfile
from pathlib import Path

# Add ccg_collab to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.core.paths import (
    resolve_existing_base_dir,
    resolve_init_base_dir,
    add_base_dir_arg,
)


def test_resolve_existing_with_cli_arg():
    """Test resolve_existing_base_dir with --base-dir argument."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / ".omc" / "collaboration").mkdir(parents=True)

        result = resolve_existing_base_dir(base_dir=str(base))
        assert result == base
        print("✓ resolve_existing_base_dir with CLI arg")


def test_resolve_existing_with_env_var():
    """Test resolve_existing_base_dir with OMC_PROJECT_ROOT env var."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        (base / ".omc" / "collaboration").mkdir(parents=True)

        os.environ["OMC_PROJECT_ROOT"] = str(base)
        try:
            result = resolve_existing_base_dir()
            assert result == base
            print("✓ resolve_existing_base_dir with env var")
        finally:
            del os.environ["OMC_PROJECT_ROOT"]


def test_resolve_existing_invalid_env():
    """Test resolve_existing_base_dir with invalid OMC_PROJECT_ROOT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)  # No .omc/collaboration

        os.environ["OMC_PROJECT_ROOT"] = str(base)
        try:
            resolve_existing_base_dir()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "OMC_PROJECT_ROOT" in str(e)
            print("✓ resolve_existing_base_dir invalid env raises error")
        finally:
            del os.environ["OMC_PROJECT_ROOT"]


def test_resolve_init_returns_tuple():
    """Test resolve_init_base_dir returns (Path, source) tuple."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = resolve_init_base_dir(base_dir=tmpdir)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Path)
        assert result[1] == "--base-dir"
        print("✓ resolve_init_base_dir returns (Path, source)")


def test_cli_priority_over_env():
    """Test CLI argument takes priority over env var."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_cli = Path(tmpdir) / "cli"
        base_env = Path(tmpdir) / "env"

        (base_cli / ".omc" / "collaboration").mkdir(parents=True)
        (base_env / ".omc" / "collaboration").mkdir(parents=True)

        os.environ["OMC_PROJECT_ROOT"] = str(base_env)
        try:
            result = resolve_existing_base_dir(base_dir=str(base_cli))
            assert result == base_cli
            print("✓ CLI arg takes priority over env var")
        finally:
            del os.environ["OMC_PROJECT_ROOT"]


if __name__ == "__main__":
    print("=== ccg_collab.core.paths Tests ===\n")

    tests = [
        test_resolve_existing_with_cli_arg,
        test_resolve_existing_with_env_var,
        test_resolve_existing_invalid_env,
        test_resolve_init_returns_tuple,
        test_cli_priority_over_env,
    ]

    failed = 0
    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(0 if failed == 0 else 1)
