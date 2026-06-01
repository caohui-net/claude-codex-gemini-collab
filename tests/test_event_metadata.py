#!/usr/bin/env python3
"""Tests for P2 event metadata enrichment."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collab_event import append_event
from collab_init import init_collaboration


class EventMetadataTests(unittest.TestCase):
    """Test event metadata enrichment (reason + logs)."""

    def test_blocked_requires_reason(self):
        """blocked event must have reason in details."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            init_collaboration(tmp_dir)

            # Try blocked without reason - should fail
            result = append_event(tmp_dir, "blocked", "claude", "TASK-1", "blocked", details={})
            self.assertEqual(result, 1, "blocked without reason should fail")

            # blocked with reason - should succeed
            result = append_event(tmp_dir, "blocked", "claude", "TASK-1", "blocked",
                                details={"reason": "Missing dependency"})
            self.assertEqual(result, 0, "blocked with reason should succeed")


if __name__ == "__main__":
    unittest.main()
