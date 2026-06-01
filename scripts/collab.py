#!/usr/bin/env python3
"""Unified entry point for claude-codex-gemini-collab operations."""
import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

COMMANDS = {
    "help": "Show available commands",
    "status": "Display collaboration status",
    "validate": "Validate collaboration state",
    "doctor": "Run diagnostic checks",
    "init": "Initialize collaboration",
    "task": "Task operations (create/claim/complete)",
    "handoff": "Handoff task to another agent",
}

def show_help():
    """Show available commands."""
    print("🛠️ [Skill: Collab] Available commands:\n")
    for cmd, desc in COMMANDS.items():
        print(f"  {cmd:12} - {desc}")
    print("\nUsage:")
    print("  python3 scripts/collab.py <command> [args...]")
    print("\nExamples:")
    print("  python3 scripts/collab.py status")
    print("  python3 scripts/collab.py task create \"Fix bug\"")
    print("  python3 scripts/collab.py handoff codex TASK-1")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        show_help()
        return 0

    command = sys.argv[1]
    args = sys.argv[2:]

    # Map commands to scripts
    script_map = {
        "status": "collab_status.py",
        "validate": "collab_validate.py",
        "doctor": "collab_doctor.py",
        "init": "collab_init.py",
        "task": "collab_task.py",
    }

    if command == "handoff":
        # Special handling for handoff
        if len(args) < 2:
            print("Usage: collab.py handoff <target-agent> <task-id> [message] [--base-dir DIR]")
            return 1

        # Extract --base-dir if present
        base_dir = None
        filtered_args = []
        i = 0
        while i < len(args):
            if args[i] == "--base-dir" and i + 1 < len(args):
                base_dir = args[i + 1]
                i += 2
            else:
                filtered_args.append(args[i])
                i += 1

        if len(filtered_args) < 2:
            print("Usage: collab.py handoff <target-agent> <task-id> [message] [--base-dir DIR]")
            return 1

        target_agent, task_id = filtered_args[0], filtered_args[1]
        message = filtered_args[2] if len(filtered_args) > 2 else f"handoff to {target_agent}"

        # Get current owner from task state
        import json
        from pathlib import Path as P
        from collab_paths import resolve_existing_base_dir
        try:
            base = resolve_existing_base_dir(base_dir)
            state_file = base / ".omc" / "collaboration" / "state.json"
            with open(state_file) as f:
                state = json.load(f)
            requester = state.get("active_agent", "unknown")
        except Exception as e:
            print(f"❌ Failed to read state: {e}")
            requester = "unknown"

        script_args = ["handoff_requested", requester, task_id, message, "--target-agent", target_agent]
        if base_dir:
            script_args.extend(["--base-dir", base_dir])
        script = "collab_event.py"
    elif command in script_map:
        script = script_map[command]
        script_args = args
    else:
        print(f"Unknown command: {command}")
        print("Run 'collab.py help' for available commands")
        return 1

    # Execute the script
    script_path = SCRIPT_DIR / script
    result = subprocess.run(
        ["python3", str(script_path)] + script_args,
        cwd=Path.cwd()
    )
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
