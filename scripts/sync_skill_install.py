#!/usr/bin/env python3
"""Sync SKILL.md to all installation paths."""
import shutil
from pathlib import Path

source = Path("SKILL.md")
if not source.exists():
    print(f"✗ Source {source} not found")
    exit(1)

targets = [
    Path(".omc/skills/claude-codex-gemini-collab/SKILL.md"),
    Path.home() / ".claude/skills/claude-codex-gemini-collab/SKILL.md",
    Path.home() / ".omc/skills/claude-codex-gemini-collab/SKILL.md"
]

for target in targets:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"✓ Synced to {target}")

print(f"\n✓ All paths synced to version {source.stat().st_mtime}")
