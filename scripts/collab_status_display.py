#!/usr/bin/env python3
"""Runtime status display for collab discuss command."""

import json
import os
import subprocess
from pathlib import Path


def show_runtime_status(base_dir: str = None):
    """Display runtime status with color formatting."""
    # Colors
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{BOLD}{CYAN}━━━ Runtime Status ━━━{RESET}")

    # TMUX info
    tmux_session = os.environ.get("TMUX_SESSION") or subprocess.run(
        ["tmux", "display-message", "-p", "#S"],
        capture_output=True, text=True, timeout=1
    ).stdout.strip() if subprocess.run(["which", "tmux"], capture_output=True).returncode == 0 else "none"

    # Claude session
    claude_session = os.environ.get("CLAUDE_CODE_SESSION_ID", "N/A")[:8]

    # Collaboration state
    if base_dir:
        state_file = Path(base_dir) / ".omc/collaboration/state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            task_status = state.get("status", "N/A")
            current_task = state.get("current_task", "N/A")
        else:
            task_status = "idle"
            current_task = "none"
    else:
        task_status = "N/A"
        current_task = "N/A"

    # Display
    print(f"{GREEN}TMUX{RESET}: {tmux_session}  {GREEN}Claude{RESET}: {claude_session}..  {GREEN}Status{RESET}: {task_status}")
    if current_task != "none" and current_task != "N/A":
        print(f"{YELLOW}Task{RESET}: {current_task[:60]}...")
    print(f"{CYAN}━━━━━━━━━━━━━━━━━━{RESET}\n")


if __name__ == "__main__":
    show_runtime_status()
