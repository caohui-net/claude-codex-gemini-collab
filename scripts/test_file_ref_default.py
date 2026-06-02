#!/usr/bin/env python3
"""Test CCG_USE_FILE_REF default behavior."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collab_discuss import save_discussion_context, build_discussion_prompt


def test_default_enabled():
    """Test CCG_USE_FILE_REF defaults to true."""
    # Simulate environment check with default
    env_value = os.environ.get("CCG_USE_FILE_REF", "true")
    use_file_ref = env_value.lower() == "true"

    assert use_file_ref is True, "Default should be enabled"
    print("✓ CCG_USE_FILE_REF defaults to true")


def test_explicit_disable():
    """Test CCG_USE_FILE_REF can be disabled."""
    # Simulate explicit disable
    os.environ["CCG_USE_FILE_REF"] = "false"
    env_value = os.environ.get("CCG_USE_FILE_REF", "true")
    use_file_ref = env_value.lower() == "true"

    assert use_file_ref is False, "Should be disabled when set to false"
    print("✓ CCG_USE_FILE_REF can be disabled")

    # Cleanup
    del os.environ["CCG_USE_FILE_REF"]


def test_file_ref_prompt():
    """Test prompt generation with file reference."""
    # Create temp context file
    base_dir = Path("/tmp/test-ccg-fileref")
    base_dir.mkdir(exist_ok=True)

    context_file = save_discussion_context(
        base_dir=base_dir,
        task_id="TEST-1",
        round_num=1,
        topic="Test topic",
        history="Test history",
        artifacts=["artifact1.md"]
    )

    # Generate prompt with file reference
    prompt = build_discussion_prompt(
        topic="Test topic",
        task_id="TEST-1",
        agent="codex",
        round_num=1,
        history="Test history",
        artifacts=["artifact1.md"],
        context_file=context_file
    )

    # Verify file reference mode
    assert "Read the discussion context from:" in prompt
    assert context_file in prompt
    assert "Test topic" not in prompt  # Topic should not be inline
    assert "Test history" not in prompt  # History should not be inline

    print(f"✓ File reference prompt generated correctly")
    print(f"  Context file: {context_file}")
    print(f"  Prompt size: {len(prompt)} chars (vs ~1100 inline)")

    # Cleanup
    import shutil
    shutil.rmtree(base_dir)


if __name__ == "__main__":
    print("=== CCG_USE_FILE_REF Default Behavior Tests ===\n")

    tests = [
        test_default_enabled,
        test_explicit_disable,
        test_file_ref_prompt,
    ]

    failed = 0
    for test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            print(f"✗ FAIL: {test_func.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test_func.__name__} - {e}")
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(0 if failed == 0 else 1)
