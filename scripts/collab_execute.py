#!/usr/bin/env python3
"""
Execution and verification orchestrator for collaboration consensus.

Usage:
    python3 scripts/collab_execute.py <task_id>
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from execution_state_machine import ExecutionStateMachine, Phase
from path_validator import validate_path


def load_consensus(base_dir: Path, task_id: str) -> dict:
    """Load consensus decision from task directory."""
    consensus_path = base_dir / ".omc/collaboration/tasks" / task_id / "consensus.json"

    if not consensus_path.exists():
        print(f"❌ Consensus file not found: {consensus_path}")
        sys.exit(1)

    with open(consensus_path) as f:
        return json.load(f)


def require_approval(consensus: dict) -> bool:
    """Require user approval before execution."""
    print("\n⚠️  Execution requires approval:")
    print(f"  Decision: {consensus.get('decision', 'N/A')[:100]}...")
    print(f"  Tasks: {len(consensus.get('tasks', []))}")

    response = input("\nProceed with execution? (yes/no): ").strip().lower()
    return response == "yes"


def create_snapshot(base_dir: Path) -> dict:
    """Create git snapshot before execution with rollback capability."""
    snapshot = {"head": "", "stash": "", "timestamp": "", "has_changes": False}

    try:
        # Capture HEAD
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        snapshot["head"] = result.stdout.strip()

        # Check for changes (staged, unstaged, untracked)
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        snapshot["has_changes"] = bool(status_result.stdout.strip())

        # Create stash for full worktree state (includes untracked)
        if snapshot["has_changes"]:
            stash_result = subprocess.run(
                ["git", "stash", "create"],
                cwd=base_dir,
                capture_output=True,
                text=True,
                check=True
            )
            snapshot["stash"] = stash_result.stdout.strip()

        snapshot["timestamp"] = subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            capture_output=True,
            text=True
        ).stdout.strip()

        print(f"\n📸 Snapshot: HEAD={snapshot['head'][:8]}, changes={snapshot['has_changes']}")
        if snapshot["stash"]:
            print(f"   Stash: {snapshot['stash'][:8]} (rollback enabled)")

        return snapshot

    except subprocess.CalledProcessError:
        print("\n⚠️  No git repository, snapshot disabled")
        return snapshot


def rollback_snapshot(base_dir: Path, snapshot: dict) -> bool:
    """Rollback to snapshot state."""
    if not snapshot.get("head"):
        print("\n⚠️  No snapshot to rollback to")
        return False

    try:
        # Reset to snapshot HEAD
        subprocess.run(
            ["git", "reset", "--hard", snapshot["head"]],
            cwd=base_dir,
            check=True,
            capture_output=True
        )

        # Restore stashed changes if any
        if snapshot.get("stash"):
            subprocess.run(
                ["git", "stash", "apply", snapshot["stash"]],
                cwd=base_dir,
                check=True,
                capture_output=True
            )

        print(f"\n↩️  Rolled back to snapshot {snapshot['head'][:8]}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Rollback failed: {e}")
        return False


def audit_execution(base_dir: Path, snapshot: dict) -> list:
    """Audit file changes after execution."""
    if not snapshot.get("head"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", snapshot["head"]],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        changed_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        if changed_files:
            print(f"\n📝 Audit: {len(changed_files)} file(s) changed")
            for f in changed_files[:5]:
                print(f"  - {f}")
            if len(changed_files) > 5:
                print(f"  ... and {len(changed_files) - 5} more")
        else:
            print("\n📝 Audit: No files changed")

        return changed_files
    except subprocess.CalledProcessError:
        print("\n⚠️  Audit failed")
        return []


def collect_evidence(base_dir: Path, task_id: str, changed_files: list) -> dict:
    """Collect execution evidence for verification."""
    evidence = {
        "task_id": task_id,
        "timestamp": subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            capture_output=True,
            text=True
        ).stdout.strip(),
        "changed_files": changed_files,
        "file_count": len(changed_files)
    }

    # Save evidence to task directory
    evidence_path = base_dir / ".omc/collaboration/tasks" / task_id / "evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"\n📋 Evidence collected: {evidence_path}")
    return evidence


def verify_execution(evidence: dict, consensus: dict) -> bool:
    """Verify execution succeeded based on evidence completeness."""
    issues = []

    # Check evidence completeness
    required_fields = ["task_id", "timestamp", "changed_files", "file_count"]
    for field in required_fields:
        if field not in evidence:
            issues.append(f"Missing evidence field: {field}")

    # Check if changes match expectations
    tasks = consensus.get("tasks", [])
    if not tasks:
        # No tasks in consensus - no changes expected, valid
        print("\n✅ Verification passed: No tasks, no changes (valid)")
        return True

    # Tasks exist - verify changes occurred
    if evidence.get("file_count", 0) == 0:
        issues.append("No file changes detected")

    # Validate against consensus expectations
    target_files = {task.get("target_file") for task in tasks if task.get("target_file")}
    changed_files = set(evidence.get("changed_files", []))

    # Check if any expected targets were modified
    if target_files and not target_files.intersection(changed_files):
        issues.append(f"Expected targets not modified: {target_files}")

    if issues:
        print("\n❌ Verification failed:")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print("\n✅ Verification passed: Evidence complete")
    return True


def validate_target_files(consensus: dict, base_dir: Path) -> tuple[bool, list]:
    """Validate target files from consensus against security policy."""
    tasks = consensus.get("tasks", [])
    if not tasks:
        print("\n⚠️  No tasks in consensus, skipping target validation")
        return True, []

    violations = []
    for task in tasks:
        target_file = task.get("target_file")
        if target_file:
            valid, error = validate_path(target_file, base_dir)
            if not valid:
                violations.append(f"{target_file}: {error}")

    if violations:
        print(f"\n❌ Target file validation failed:")
        for v in violations:
            print(f"  - {v}")
        return False, violations

    print(f"\n✅ Target files validated ({len(tasks)} task(s))")
    return True, []


def validate_changed_files(changed_files: list, base_dir: Path) -> tuple[bool, list]:
    """Validate changed files against security policy."""
    if not changed_files:
        return True, []

    violations = []
    for file_path in changed_files:
        valid, error = validate_path(file_path, base_dir)
        if not valid:
            violations.append(f"{file_path}: {error}")

    if violations:
        print(f"\n❌ Changed file validation failed:")
        for v in violations[:5]:
            print(f"  - {v}")
        if len(violations) > 5:
            print(f"  ... and {len(violations) - 5} more")
        return False, violations

    print(f"\n✅ Changed files validated ({len(changed_files)} file(s))")
    return True, []


def main():
    parser = argparse.ArgumentParser(description="Execute collaboration consensus")
    parser.add_argument("task_id", help="Task ID to execute")
    parser.add_argument("--base-dir", type=Path, default=Path.cwd(),
                       help="Base directory (default: current)")
    parser.add_argument("--skip-approval", action="store_true",
                       help="Skip approval prompt (for testing)")

    args = parser.parse_args()

    print(f"🚀 Collaboration Execution Engine")
    print(f"Task: {args.task_id}")
    print(f"Base: {args.base_dir}")

    # Initialize state machine
    sm = ExecutionStateMachine(args.base_dir, args.task_id)
    print(f"\n📊 Current phase: {sm.state['phase']}")

    # Load consensus
    consensus = load_consensus(args.base_dir, args.task_id)
    print(f"\n📋 Consensus loaded:")
    print(f"  Decision: {consensus.get('decision', 'N/A')[:100]}...")
    print(f"  Tasks: {len(consensus.get('tasks', []))}")

    # Safety: Require approval
    if not args.skip_approval:
        if not require_approval(consensus):
            print("\n❌ Execution cancelled by user")
            sm.transition_to(Phase.FAILED)
            return 1

    # Security: Validate target files before execution
    target_valid, target_violations = validate_target_files(consensus, args.base_dir)
    if not target_valid:
        print("\n❌ Execution blocked by security policy")
        sm.transition_to(Phase.FAILED)
        return 1

    # Safety: Create snapshot before execution
    snapshot = create_snapshot(args.base_dir)

    # Transition to executing phase
    sm.transition_to(Phase.EXECUTING)

    # Execute tasks from consensus
    tasks = consensus.get("tasks", [])
    if not tasks:
        print("\n⚠️  No tasks in consensus, skipping execution")
    else:
        print(f"\n🔨 Executing {len(tasks)} task(s)...")
        for i, task in enumerate(tasks, 1):
            target_file = task.get("target_file")
            content = task.get("content", "")
            action = task.get("action", "write")

            if not target_file:
                print(f"  [{i}] Skipped: no target_file")
                continue

            target_path = args.base_dir / target_file

            try:
                if action == "write":
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(content, encoding="utf-8")
                    print(f"  [{i}] ✓ {target_file}")

                    # Add to git index so audit detects changes
                    try:
                        subprocess.run(
                            ["git", "add", str(target_path)],
                            cwd=args.base_dir,
                            capture_output=True,
                            check=False  # Don't fail if no git
                        )
                    except Exception:
                        pass  # Ignore git errors
                else:
                    print(f"  [{i}] ✗ Unknown action: {action}")
            except Exception as e:
                print(f"  [{i}] ✗ {target_file}: {e}")
                sm.transition_to(Phase.FAILED)
                return 1

    # Safety: Audit changes after execution
    changed_files = audit_execution(args.base_dir, snapshot)

    # Security: Validate changed files against policy
    changed_valid, changed_violations = validate_changed_files(changed_files, args.base_dir)
    if not changed_valid:
        print("\n❌ Execution violated security policy")
        sm.transition_to(Phase.FAILED)
        return 1

    # Transition to verifying phase
    sm.transition_to(Phase.VERIFYING)

    # Verification: Collect evidence
    evidence = collect_evidence(args.base_dir, args.task_id, changed_files)

    # Verification: Verify execution success
    success = verify_execution(evidence, consensus)

    # Mark as completed or failed based on verification
    if success:
        sm.transition_to(Phase.COMPLETED)
        print("\n✅ Execution completed successfully")
        return 0
    else:
        sm.transition_to(Phase.FAILED)
        print("\n❌ Execution verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
