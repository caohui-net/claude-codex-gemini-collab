#!/usr/bin/env python3
"""Tests for ccg_collab.discuss modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.discuss.utils import compress_history, format_history_text
from ccg_collab.discuss.artifacts import save_artifact


def test_compress_history():
    """Test compress_history with discussion events."""
    events = [
        {"task_id": "TASK-1", "type": "discussion_message", "agent": "codex", "summary": "Agree"},
        {"task_id": "TASK-1", "type": "discussion_message", "agent": "gemini", "summary": "Agree"},
        {"task_id": "TASK-2", "type": "discussion_message", "agent": "codex", "summary": "Different task"},
    ]

    result = compress_history(events, "TASK-1", max_recent=1)
    assert "codex" in result or "gemini" in result
    assert "TASK-2" not in result
    print("✓ compress_history filters by task_id")


def test_format_history_text():
    """Test format_history_text."""
    history = [
        {"agent": "codex", "content": "First message"},
        {"agent": "gemini", "summary": "Second message"},
    ]

    result = format_history_text(history, summary=False)
    assert "[codex]" in result
    assert "First message" in result
    print("✓ format_history_text formats correctly")


def test_save_artifact(tmp_path):
    """Test save_artifact creates file."""
    result = save_artifact(tmp_path, "TASK-TEST", 1, "codex", "Test content")

    artifact_path = tmp_path / result
    assert artifact_path.exists()
    assert "Test content" in artifact_path.read_text()
    print("✓ save_artifact creates file")


if __name__ == "__main__":
    import tempfile

    print("=== ccg_collab.discuss Tests ===\n")

    failed = 0
    try:
        test_compress_history()
    except Exception as e:
        print(f"✗ test_compress_history: {e}")
        failed += 1

    try:
        test_format_history_text()
    except Exception as e:
        print(f"✗ test_format_history_text: {e}")
        failed += 1

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_save_artifact(Path(tmpdir))
    except Exception as e:
        print(f"✗ test_save_artifact: {e}")
        failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {3 - failed}/3 tests passed")
    sys.exit(0 if failed == 0 else 1)
