import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from .provider import CoordinationProvider


class FilesystemCoordination(CoordinationProvider):
    """Filesystem-based coordination (backward compatible with existing behavior)."""

    def __init__(self, base_dir: str = ".omc/collaboration"):
        self.base_dir = Path(base_dir)
        self.locks_dir = self.base_dir / "locks"
        self.signals_dir = self.base_dir / "signals"
        self.actions_dir = self.base_dir / "actions"

        # Create directories if they don't exist
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.actions_dir.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        """Acquire lock using mkdir (atomic on POSIX)."""
        lock_path = self.locks_dir / f"{resource}.lock"
        try:
            lock_path.mkdir(exist_ok=False)
            lock_data = {
                "agent": agent,
                "acquired_at": time.time(),
                "timeout": timeout
            }
            (lock_path / "data.json").write_text(json.dumps(lock_data, indent=2))
            return True
        except FileExistsError:
            return False

    def release_lock(self, resource: str, agent: str) -> bool:
        """Release lock by removing directory."""
        lock_path = self.locks_dir / f"{resource}.lock"
        if lock_path.exists():
            import shutil
            shutil.rmtree(lock_path)
            return True
        return False

    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        """Send signal by creating file (polling-based fallback)."""
        timestamp = int(time.time() * 1000)
        signal_file = self.signals_dir / f"{signal}_{timestamp}.json"
        signal_data = {
            "type": signal,
            "payload": payload,
            "target": target,
            "timestamp": timestamp
        }
        signal_file.write_text(json.dumps(signal_data, indent=2))

    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for signal using polling (fallback implementation)."""
        start = time.time()
        while time.time() - start < timeout:
            for sig_file in sorted(self.signals_dir.glob(f"{signal}_*.json")):
                try:
                    data = json.loads(sig_file.read_text())
                    sig_file.unlink()  # Consume signal
                    return data
                except (json.JSONDecodeError, FileNotFoundError):
                    continue
            time.sleep(0.1)  # Poll interval
        return None

    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        """Enqueue action by creating file."""
        timestamp = int(time.time() * 1000)
        action_file = self.actions_dir / f"{target}_{action}_{timestamp}.json"
        action_data = {
            "action": action,
            "payload": payload,
            "target": target,
            "timestamp": timestamp
        }
        action_file.write_text(json.dumps(action_data, indent=2))

    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        """Claim action by reading and removing file."""
        for action_file in sorted(self.actions_dir.glob(f"{agent}_*.json")):
            try:
                data = json.loads(action_file.read_text())
                action_file.unlink()  # Consume action
                return data
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        return None
