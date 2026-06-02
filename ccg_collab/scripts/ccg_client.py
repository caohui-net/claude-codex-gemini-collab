#!/usr/bin/env python3
"""CCG Daemon Client - CLI wrapper for daemon communication."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict

import requests


def get_runtime_file() -> Path:
    """Get runtime discovery file path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "ccg-daemon.json"
    return Path.home() / ".cache" / "ccg-daemon.json"


def read_runtime_info() -> Optional[Dict]:
    """Read daemon runtime info from discovery file."""
    runtime_file = get_runtime_file()
    if not runtime_file.exists():
        return None

    try:
        return json.loads(runtime_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_daemon_running(runtime_info: Dict) -> bool:
    """Check if daemon is actually running."""
    try:
        # Check if process exists
        pid = runtime_info.get("pid")
        if pid:
            os.kill(pid, 0)  # Signal 0 just checks if process exists

        # Check if daemon responds
        port = runtime_info.get("port")
        response = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
        return response.status_code == 200
    except (OSError, requests.RequestException):
        return False


def start_daemon() -> bool:
    """Start the daemon process."""
    daemon_script = Path(__file__).parent / "ccg_daemon.py"
    venv_python = Path(__file__).parent.parent / ".venv" / "bin" / "python"

    if not venv_python.exists():
        print("❌ Virtual environment not found", file=sys.stderr)
        return False

    # Start daemon in background
    subprocess.Popen(
        [str(venv_python), str(daemon_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    # Wait for daemon to be ready
    for _ in range(30):  # 3 seconds max
        time.sleep(0.1)
        runtime_info = read_runtime_info()
        if runtime_info and is_daemon_running(runtime_info):
            return True

    return False


def get_daemon_url() -> Optional[str]:
    """Get daemon URL, starting daemon if needed."""
    # Check if daemon is disabled
    if os.environ.get("CCG_DAEMON") == "0":
        return None

    # Check if daemon is running
    runtime_info = read_runtime_info()
    if runtime_info and is_daemon_running(runtime_info):
        port = runtime_info["port"]
        return f"http://127.0.0.1:{port}"

    # Try to start daemon
    if start_daemon():
        runtime_info = read_runtime_info()
        if runtime_info:
            port = runtime_info["port"]
            return f"http://127.0.0.1:{port}"

    return None


def submit_task(task_data: dict) -> Optional[str]:
    """Submit task to daemon, with fallback to direct execution."""
    daemon_url = get_daemon_url()

    if daemon_url:
        try:
            response = requests.post(
                f"{daemon_url}/tasks/submit",
                json=task_data,
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("task_id")
        except requests.RequestException:
            pass

    # Fallback: return None to indicate direct execution needed
    return None


def get_task_status(task_id: str) -> Optional[Dict]:
    """Get task status from daemon."""
    daemon_url = get_daemon_url()

    if not daemon_url:
        return None

    try:
        response = requests.get(
            f"{daemon_url}/tasks/{task_id}/status",
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass

    return None


def cancel_task(task_id: str) -> bool:
    """Cancel task in daemon."""
    daemon_url = get_daemon_url()

    if not daemon_url:
        return False

    try:
        response = requests.post(
            f"{daemon_url}/tasks/{task_id}/cancel",
            timeout=5
        )
        return response.status_code == 200
    except requests.RequestException:
        return False
