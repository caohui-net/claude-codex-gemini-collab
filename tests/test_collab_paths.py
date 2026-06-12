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

from collab_paths import (
    find_upward_collaboration,
    find_git_root,
    resolve_existing_base_dir,
    resolve_init_base_dir,
)
from collab_init import init_collaboration


class CollabPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_find_upward_collaboration_from_root(self):
        """Test finding .collab from repo root."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)

        found = find_upward_collaboration(self.base)
        self.assertEqual(found, self.base)

    def test_find_upward_collaboration_from_nested(self):
        """Test finding .collab from nested directory."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)

        nested = self.base / "src" / "components"
        nested.mkdir(parents=True)

        found = find_upward_collaboration(nested)
        self.assertEqual(found, self.base)

    def test_find_upward_collaboration_not_found(self):
        """Test finding .collab when it doesn't exist."""
        found = find_upward_collaboration(self.base)
        self.assertIsNone(found)

    def test_resolve_existing_base_dir_with_explicit_base(self):
        """Test resolve_existing_base_dir with --base-dir."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)

        result = resolve_existing_base_dir(str(self.base))
        self.assertEqual(result, self.base)

    def test_resolve_existing_base_dir_upward_search(self):
        """Test resolve_existing_base_dir finds parent state."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)

        nested = self.base / "src" / "components"
        nested.mkdir(parents=True)

        result = resolve_existing_base_dir(None, nested)
        self.assertEqual(result, self.base)

    def test_resolve_existing_base_dir_fails_when_not_found(self):
        """Test resolve_existing_base_dir raises ValueError when not found."""
        with self.assertRaises(ValueError) as ctx:
            resolve_existing_base_dir(None, self.base)
        self.assertIn("No .collab directory found", str(ctx.exception))

    def test_resolve_init_base_dir_with_explicit_base(self):
        """Test resolve_init_base_dir with --base-dir."""
        result, source = resolve_init_base_dir(str(self.base))
        self.assertEqual(result, self.base)
        self.assertEqual(source, "--base-dir")

    def test_resolve_init_base_dir_reuses_existing_state(self):
        """Test resolve_init_base_dir reuses existing parent state (avoids nested)."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)

        nested = self.base / "src" / "components"
        nested.mkdir(parents=True)

        result, source = resolve_init_base_dir(None, nested)
        self.assertEqual(result, self.base)
        self.assertEqual(source, "existing")

    def test_resolve_init_base_dir_falls_back_to_cwd(self):
        """Test resolve_init_base_dir falls back to cwd when no git repo."""
        result, source = resolve_init_base_dir(None, self.base)
        self.assertEqual(result, self.base)
        self.assertEqual(source, "cwd")

    def test_resolve_existing_base_dir_validates_explicit_path(self):
        """Test resolve_existing_base_dir rejects invalid --base-dir."""
        wrong_path = self.base / "wrong"
        wrong_path.mkdir()

        with self.assertRaises(ValueError) as ctx:
            resolve_existing_base_dir(str(wrong_path))
        self.assertIn("No .collab directory found at", str(ctx.exception))

    def test_resolve_init_base_dir_uses_git_root(self):
        """Test resolve_init_base_dir uses git root when available."""
        subprocess.run(["git", "init"], cwd=self.base, capture_output=True)

        nested = self.base / "src" / "components"
        nested.mkdir(parents=True)

        result, source = resolve_init_base_dir(None, nested)
        self.assertEqual(result, self.base)
        self.assertEqual(source, "git")

    def test_nested_cli_command_execution(self):
        """Test CLI command works from nested directory."""
        collab_dir = self.base / ".collab"
        collab_dir.mkdir(parents=True)
        init_collaboration(self.base, "test")

        nested = self.base / "src" / "components"
        nested.mkdir(parents=True)

        # Run actual CLI script from nested directory
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "collab_status.py")],
            cwd=nested,
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("initialized", result.stdout)


if __name__ == "__main__":
    unittest.main()
