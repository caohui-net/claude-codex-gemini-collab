#!/usr/bin/env python3
"""Diagnostic tool for claude-codex-gemini-collab skill activation."""
import json
import sys
from pathlib import Path

def check_version_consistency():
    """Check SKILL.md version across all installation paths."""
    print("🔍 Checking version consistency...")

    paths = [
        Path("SKILL.md"),
        Path(".omc/skills/claude-codex-gemini-collab/SKILL.md"),
        Path.home() / ".claude/skills/claude-codex-gemini-collab/SKILL.md",
        Path.home() / ".omc/skills/claude-codex-gemini-collab/SKILL.md"
    ]

    versions = {}
    for path in paths:
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.startswith("version:"):
                        versions[str(path)] = line.strip()
                        break
        else:
            versions[str(path)] = "NOT FOUND"

    unique_versions = set(versions.values())
    if len(unique_versions) == 1:
        print(f"  ✓ All paths have same version: {list(unique_versions)[0]}")
        return True
    else:
        print("  ✗ Version mismatch detected:")
        for path, version in versions.items():
            print(f"    {path}: {version}")
        print("\n  💡 Fix: Run sync script to update all paths:")
        print("     python3 scripts/sync_skill_install.py")
        return False

def check_skill_overrides():
    """Check skillOverrides configuration."""
    print("\n🔍 Checking skillOverrides...")

    settings_path = Path(".claude/settings.local.json")
    if not settings_path.exists():
        print("  ⚠ .claude/settings.local.json not found")
        print("\n  💡 Fix: Create settings file with:")
        print('     echo \'{"skillOverrides": {"ccg": "off"}}\' > .claude/settings.local.json')
        return False

    with open(settings_path) as f:
        settings = json.load(f)

    if "skillOverrides" not in settings:
        print("  ✗ No skillOverrides configured")
        print("\n  💡 Fix: Add to .claude/settings.local.json:")
        print('     {"skillOverrides": {"ccg": "off"}}')
        return False

    if "ccg" in settings["skillOverrides"]:
        mode = settings["skillOverrides"]["ccg"]
        print(f"  ✓ OMC ccg override: {mode}")
        return True
    else:
        print("  ⚠ OMC ccg not overridden (may conflict)")
        print("\n  💡 Fix: Add to skillOverrides in .claude/settings.local.json:")
        print('     "ccg": "off"')
        return False

def check_yaml_syntax():
    """Check SKILL.md YAML frontmatter syntax."""
    print("\n🔍 Checking YAML syntax...")

    skill_path = Path("SKILL.md")
    if not skill_path.exists():
        print("  ✗ SKILL.md not found")
        return False

    with open(skill_path) as f:
        content = f.read()

    if not content.startswith("---"):
        print("  ✗ Missing YAML frontmatter")
        return False

    # Basic checks
    required_fields = ["name:", "aliases:", "description:", "version:"]
    missing = [field for field in required_fields if field not in content[:500]]

    if missing:
        print(f"  ✗ Missing required fields: {', '.join(missing)}")
        return False

    print("  ✓ YAML frontmatter looks valid")
    return True

def main():
    print("🛠️ [Skill: Collab Doctor] Running diagnostics...\n")

    results = [
        check_version_consistency(),
        check_skill_overrides(),
        check_yaml_syntax()
    ]

    print("\n" + "="*50)
    if all(results):
        print("✓ All checks passed")
        print("\n⚠ IMPORTANT: Restart Claude Code session for changes to take effect")
        return 0
    else:
        print("✗ Some checks failed - review output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
