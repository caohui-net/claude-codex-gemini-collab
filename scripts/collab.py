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
    "repair": "Repair corrupted collaboration state",
    "doctor": "Run diagnostic checks",
    "init": "Initialize collaboration",
    "task": "Task operations (create/claim/complete)",
    "handoff": "Handoff task to another agent",
    "discuss": "Multi-agent discussion to consensus",
}

def show_help():
    """Show available commands."""
    print("🛠️ [Skill: Collab] Available commands:\n")
    for cmd, desc in COMMANDS.items():
        print(f"  {cmd:12} - {desc}")
    print("\nUsage:")
    print("  python3 scripts/collab.py [--agent AGENT] <command> [args...]")
    print("\nGlobal Options:")
    print("  --agent AGENT    Agent identity (required for task/handoff operations)")
    print("\nExamples:")
    print("  python3 scripts/collab.py status")
    print("  python3 scripts/collab.py --agent claude task create \"Fix bug\"")
    print("  python3 scripts/collab.py --agent claude handoff codex TASK-1")

def main():
    # Parse global --agent flag
    agent = None
    argv = sys.argv[1:]

    if len(argv) >= 2 and argv[0] == "--agent":
        agent = argv[1]
        argv = argv[2:]

    if len(argv) < 1 or argv[0] in ["-h", "--help", "help"]:
        show_help()
        return 0

    command = argv[0]
    args = argv[1:]

    # Map commands to scripts
    script_map = {
        "status": "collab_status.py",
        "validate": "collab_validate.py",
        "repair": "collab_validate.py",
        "doctor": "collab_doctor.py",
        "init": "collab_init.py",
        "task": "collab_task.py",
        "discuss": "collab_discuss.py",
    }

    if command == "handoff":
        # Require explicit --agent for handoff
        if not agent:
            print("❌ --agent required for handoff operations")
            print("Usage: collab.py --agent <agent> handoff <target-agent> <task-id> [message] [--base-dir DIR]")
            return 1

        if len(args) < 2:
            print("Usage: collab.py --agent <agent> handoff <target-agent> <task-id> [message] [--base-dir DIR]")
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
            print("Usage: collab.py --agent <agent> handoff <target-agent> <task-id> [message] [--base-dir DIR]")
            return 1

        target_agent, task_id = filtered_args[0], filtered_args[1]
        message = filtered_args[2] if len(filtered_args) > 2 else f"handoff to {target_agent}"

        script_args = ["handoff_requested", agent, task_id, message, "--target-agent", target_agent]
        if base_dir:
            script_args.extend(["--base-dir", base_dir])
        script = "collab_event.py"
    elif command in script_map:
        script = script_map[command]
        if command == "repair":
            script_args = ["repair"] + args
        elif command == "discuss":
            # Prepend discuss subcommand for collab_discuss.py
            script_args = ["discuss"] + args
        elif command == "task" and agent:
            # Pass agent as positional argument for task operations
            script_args = args + [agent]
        else:
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
