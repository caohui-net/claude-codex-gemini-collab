#!/usr/bin/env python3
"""Install claude-codex-gemini-collab skill with all dependencies."""
import shutil
from pathlib import Path

# Required files
REQUIRED_FILES = [
    "SKILL.md",
    "scripts/collab_init.py",
    "scripts/collab_validate.py",
    "scripts/collab_status.py",
    "scripts/collab_task.py",
    "scripts/collab_event.py",
    "scripts/collab_discuss.py",
    "scripts/collab_status_display.py",
    "scripts/collab_execute.py",
    "scripts/agent_cli.py",
    "scripts/agentmemory_bridge.py",
    "scripts/models.py",
    "scripts/collab_state.py",
    "scripts/collab_paths.py",
    "scripts/discussion_enhancements.py",
    "scripts/rmux_utils.py",
    "scripts/ccg_client.py",
    "scripts/loop_detector.py",
    "scripts/context_compactor.py",
    "scripts/execution_review.py",
    "scripts/execution_state_machine.py",
    "scripts/path_validator.py",
    "scripts/mcp_adapter.py",
]

# Installation targets
TARGETS = [
    Path.home() / ".claude/skills/claude-codex-gemini-collab",
    Path.home() / ".omc/skills/claude-codex-gemini-collab",
]

def main():
    project_root = Path(__file__).parent.parent

    for target_base in TARGETS:
        target_base.mkdir(parents=True, exist_ok=True)
        target_scripts = target_base / "scripts"
        target_scripts.mkdir(exist_ok=True)

        for file_path in REQUIRED_FILES:
            source = project_root / file_path
            if not source.exists():
                print(f"⚠️  {file_path} not found, skipping")
                continue

            if file_path == "SKILL.md":
                target = target_base / "SKILL.md"
            else:
                target = target_base / file_path

            shutil.copy2(source, target)
            print(f"✓ {file_path} → {target}")

        print(f"\n✅ Installed to {target_base}\n")

    print("✅ Installation complete")

if __name__ == "__main__":
    main()
