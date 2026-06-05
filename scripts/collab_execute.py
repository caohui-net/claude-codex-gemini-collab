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


def create_snapshot(base_dir: Path) -> str:
    """Create git snapshot before execution."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()
        print(f"\n📸 Snapshot: {commit_hash[:8]}")
        return commit_hash
    except subprocess.CalledProcessError:
        print("\n⚠️  No git repository, skipping snapshot")
        return ""


def audit_execution(base_dir: Path, snapshot: str) -> list:
    """Audit file changes after execution."""
    if not snapshot:
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", snapshot],
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
    """Verify execution succeeded based on evidence."""
    # Minimal verification: check if any files changed
    success = evidence["file_count"] > 0

    if success:
        print("\n✅ Verification: Execution produced changes")
    else:
        print("\n⚠️  Verification: No changes detected")

    return success


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

    # Safety: Create snapshot before execution
    snapshot = create_snapshot(args.base_dir)

    # Transition to executing phase
    sm.transition_to(Phase.EXECUTING)

    # TODO: Implement actual execution logic
    print("\n⚠️  Execution logic not yet implemented")

    # Safety: Audit changes after execution
    changed_files = audit_execution(args.base_dir, snapshot)

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
