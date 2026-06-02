#!/usr/bin/env python3
"""Tests for discuss routing trigger patterns."""

import pytest
from pathlib import Path


def test_skill_md_has_discuss_triggers():
    """Verify SKILL.md documents discuss routing triggers."""
    skill_md = Path(__file__).parent.parent / "SKILL.md"
    assert skill_md.exists(), "SKILL.md not found"

    content = skill_md.read_text()

    # Verify positive trigger examples exist
    positive_triggers = [
        "start Claude Codex Gemini collaboration",
        "handoff to Codex",
        "handoff to Gemini",
        "multi-model discussion"
    ]

    for trigger in positive_triggers:
        assert trigger in content, f"Missing trigger example: {trigger}"

    # Verify negative examples exist (should NOT trigger)
    negative_examples = [
        "discuss the implementation",
        "帮我review一下"
    ]

    for neg in negative_examples:
        assert neg in content, f"Missing negative example: {neg}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
