from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum


class CoordinationBackend(Enum):
    FILESYSTEM = "filesystem"
    AGENTMEMORY = "agentmemory"


class CoordinationProvider(ABC):
    """Abstract coordination provider interface for multi-agent coordination."""

    @abstractmethod
    def acquire_lock(self, resource: str, agent: str, timeout: float) -> bool:
        """Acquire a lock/lease on a resource.

        Args:
            resource: Resource identifier
            agent: Agent identifier acquiring the lock
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        pass

    @abstractmethod
    def release_lock(self, resource: str, agent: str) -> bool:
        """Release a lock/lease.

        Args:
            resource: Resource identifier
            agent: Agent identifier releasing the lock

        Returns:
            True if lock released, False otherwise
        """
        pass

    @abstractmethod
    def send_signal(self, signal: str, payload: Dict[str, Any], target: Optional[str] = None):
        """Send a signal to agents (pub/sub).

        Args:
            signal: Signal type identifier
            payload: Signal payload data
            target: Optional target agent, None for broadcast
        """
        pass

    @abstractmethod
    def wait_signal(self, signal: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for a signal with timeout.

        Args:
            signal: Signal type to wait for
            timeout: Wait timeout in seconds

        Returns:
            Signal data if received, None if timeout
        """
        pass

    @abstractmethod
    def enqueue_action(self, action: str, payload: Dict[str, Any], target: str):
        """Enqueue an action for an agent.

        Args:
            action: Action type identifier
            payload: Action payload data
            target: Target agent identifier
        """
        pass

    @abstractmethod
    def claim_action(self, agent: str) -> Optional[Dict[str, Any]]:
        """Claim next action from queue.

        Args:
            agent: Agent identifier claiming the action

        Returns:
            Action data if available, None if queue empty
        """
        pass
