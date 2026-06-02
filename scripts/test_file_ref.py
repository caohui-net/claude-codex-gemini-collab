#!/usr/bin/env python3
"""Test file-reference prompt construction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_discuss import build_discussion_prompt, save_discussion_context


def test_inline_mode():
    """Test backward-compatible inline mode."""
    prompt = build_discussion_prompt(
        topic="Test topic",
        task_id="TEST-1",
        agent="codex",
        round_num=1,
        history="Previous: consensus not reached",
        artifacts=["artifact1.md", "artifact2.md"],
        context_file=None
    )

    assert "Test topic" in prompt
    assert "Previous: consensus not reached" in prompt
    assert "artifact1.md" in prompt
    assert "[RESPONSE_START]" in prompt
    print("✓ Inline mode works")


def test_file_ref_mode():
    """Test file-reference mode."""
    prompt = build_discussion_prompt(
        topic="Test topic",
        task_id="TEST-1",
        agent="codex",
        round_num=1,
        history="Previous: consensus not reached",
        artifacts=["artifact1.md"],
        context_file=".omc/collaboration/context/TEST-1-r1-context.md"
    )

    assert "Test topic" not in prompt
    assert "Previous: consensus" not in prompt
    assert "Read the discussion context from:" in prompt
    assert "TEST-1-r1-context.md" in prompt
    assert "[RESPONSE_START]" in prompt
    print("✓ File-reference mode works")


def test_save_context():
    """Test context file creation."""
    base_dir = Path("/tmp/test-ccg")
    base_dir.mkdir(exist_ok=True)

    context_path = save_discussion_context(
        base_dir=base_dir,
        task_id="TEST-1",
        round_num=1,
        topic="Test topic",
        history="Previous discussion",
        artifacts=["artifact1.md"]
    )

    full_path = base_dir / context_path
    assert full_path.exists()

    content = full_path.read_text()
    assert "Test topic" in content
    assert "Previous discussion" in content
    assert "artifact1.md" in content
    print(f"✓ Context file created: {context_path}")

    # Cleanup
    import shutil
    shutil.rmtree(base_dir)


if __name__ == "__main__":
    print("=== File-Reference Mode Tests ===\n")

    try:
        test_inline_mode()
        test_file_ref_mode()
        test_save_context()
        print("\n✅ All tests passed")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
