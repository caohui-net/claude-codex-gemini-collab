import time
from typing import Optional, Dict, Any
from iii import register_worker
from .provider import CoordinationProvider


class AgentMemoryCoordination(CoordinationProvider):
    """agentmemory-based coordination using iii-sdk.

    Uses iii-engine WebSocket connection (ws://localhost:49134) to call
    coordination functions: lease, signal, action APIs.
    """

    def __init__(self, ws_url: str = "ws://localhost:49134"):
        self.ws_url = ws_url
        self.client = register_worker(self.ws_url)

    def _trigger(self, function_id: str, payload: Dict[str, Any]) -> Any:
        """Call iii-engine function via trigger."""
        if not self.client:
            raise RuntimeError("iii-engine client not connected")

        result = self.client.trigger({
            "function_id": function_id,
            "payload": payload
        })
        return result

    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        """Acquire exclusive lease using mem::lease-acquire."""
        try:
            result = self._trigger("mem::lease-acquire", {
                "action_id": resource,
                "worker_id": agent,
                "duration_ms": int(timeout * 1000)
            })
            return result.get("success", False)
        except Exception:
            return False

    def release_lock(self, resource: str, agent: str) -> bool:
        """Release lease using mem::lease-release."""
        try:
            result = self._trigger("mem::lease-release", {
                "action_id": resource,
                "worker_id": agent
            })
            return result.get("success", False)
        except Exception:
            return False

    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        """Send signal using mem::signal-send."""
        self._trigger("mem::signal-send", {
            "to": target or "broadcast",
            "subject": signal,
            "body": str(payload),
            "metadata": payload
        })

    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for signal using mem::signal-read with polling."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = self._trigger("mem::signal-read", {
                    "worker_id": "self",
                    "mark_read": True
                })
                if result and result.get("messages"):
                    for msg in result["messages"]:
                        if msg.get("subject") == signal:
                            return msg.get("metadata", {})
            except Exception:
                pass
            time.sleep(0.1)
        return None

    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        """Enqueue action using mem::action-create."""
        self._trigger("mem::action-create", {
            "title": action,
            "description": str(payload),
            "dependencies": [],
            "priority": 5,
            "metadata": {"target": target, **payload}
        })

    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        """Claim next action using mem::next."""
        try:
            result = self._trigger("mem::next", {
                "worker_id": agent,
                "project": "collab"
            })
            return result if result else None
        except Exception:
            return None
