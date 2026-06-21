#!/usr/bin/env python3
"""Runtime status display for collab discuss command."""

import json
import os
import subprocess
from pathlib import Path


def show_runtime_status(base_dir: str = None, task_id: str = None, topic: str = None,
                        participants: list = None, mode: str = None, max_rounds: int = None,
                        use_tmux: bool = None, tmux_version: str = None):
    """Display runtime status with color formatting (best-effort)."""
    # Colors
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{BOLD}{CYAN}━━━ Runtime Status ━━━{RESET}")

    # TMUX info - detect rmux version dynamically
    if use_tmux is not None:
        if use_tmux:
            # Try to get actual rmux version (prefer system install)
            rmux_paths = ["/usr/bin/rmux", "/usr/local/bin/rmux",
                         os.path.expanduser("~/.local/bin/rmux"),
                         os.path.expanduser("~/.cargo/bin/rmux"),
                         "rmux"]
            version_detected = False
            for rmux_cmd in rmux_paths:
                try:
                    result = subprocess.run([rmux_cmd, "-V"], capture_output=True, text=True, timeout=1)
                    if result.returncode == 0 and result.stdout.strip():
                        tmux_status = f"✓ {result.stdout.strip()}"
                        version_detected = True
                        break
                except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
                    continue
            if not version_detected:
                tmux_status = f"✓ {tmux_version}" if tmux_version else "✓ enabled"
        else:
            tmux_status = "✗ disabled"
    else:
        # Fallback: try to detect current session (legacy behavior)
        tmux_status = "unknown"
        try:
            tmux_env = os.environ.get("TMUX_SESSION")
            if tmux_env:
                tmux_status = tmux_env
            elif subprocess.run(["which", "tmux"], capture_output=True, timeout=1).returncode == 0:
                result = subprocess.run(["tmux", "display-message", "-p", "#S"],
                                      capture_output=True, text=True, timeout=1)
                tmux_status = result.stdout.strip() or "none"
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            tmux_status = "unavailable"

    # Claude session
    claude_session = os.environ.get("CLAUDE_CODE_SESSION_ID", "N/A")[:8]

    # Collaboration state (best-effort)
    task_status = "N/A"
    try:
        if base_dir:
            state_file = Path(base_dir) / ".collab/state.json"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                if isinstance(state, dict):
                    task_status = state.get("status", "N/A")
                else:
                    task_status = "invalid"
    except (json.JSONDecodeError, OSError, AttributeError, TypeError):
        task_status = "unknown"

    # Display
    print(f"{GREEN}RMux{RESET}: {tmux_status}  {GREEN}Claude{RESET}: {claude_session}..  {GREEN}Status{RESET}: {task_status}")

    # Participants and mode
    if participants:
        print(f"{GREEN}Participants{RESET}: {', '.join(participants)}  {GREEN}Mode{RESET}: {mode or 'full'}")

    # Rounds
    if max_rounds:
        print(f"{GREEN}Rounds{RESET}: 1/{max_rounds}")

    # Task
    if task_id:
        display_task = task_id[:60] + "..." if len(task_id) > 60 else task_id
        print(f"{YELLOW}Task{RESET}: {display_task}")

    print(f"{CYAN}━━━━━━━━━━━━━━━━━━{RESET}\n")


if __name__ == "__main__":
    show_runtime_status()
