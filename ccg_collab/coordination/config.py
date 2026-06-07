import json
from pathlib import Path
from typing import Optional
from .provider import CoordinationBackend, CoordinationProvider
from .filesystem import FilesystemCoordination
from .agentmemory import AgentMemoryCoordination


class CollabConfig:
    """Configuration manager for coordination backend selection."""

    def __init__(self, settings_path: str = ".claude/settings.json"):
        self.settings_path = Path(settings_path)
        self.settings = self._load_settings()
        self.ccg_config = self.settings.get("ccgCollab", {})

    def _load_settings(self) -> dict:
        """Load settings from file, return empty dict if not found."""
        if self.settings_path.exists():
            try:
                return json.loads(self.settings_path.read_text())
            except json.JSONDecodeError:
                return {}
        return

    @property
    def backend(self) -> CoordinationBackend:
        """Get configured backend (default: filesystem)."""
        backend_str = self.ccg_config.get("coordinationBackend", "filesystem")
        return CoordinationBackend(backend_str)

    @property
    def agentmemory_enabled(self) -> bool:
        """Check if agentmemory is explicitly enabled."""
        return self.ccg_config.get("agentmemory", {}).get("enabled", False)

    @property
    def agentmemory_url(self) -> str:
        """Get agentmemory WebSocket URL."""
        return self.ccg_config.get("agentmemory", {}).get("wsUrl", "ws://localhost:49134")

    @property
    def fallback_enabled(self) -> bool:
        """Check if fallback to filesystem is enabled."""
        return self.ccg_config.get("agentmemory", {}).get("fallbackToFilesystem", True)

    def get_coordination_provider(self) -> CoordinationProvider:
        """Get the appropriate coordination provider based on config.

        Returns:
            CoordinationProvider: Filesystem or agentmemory provider

        Logic:
            1. If backend is filesystem, return FilesystemCoordination
            2. If backend is agentmemory and enabled:
               - Try AgentMemoryCoordination
               - On error, fall back to FilesystemCoordination if enabled
            3. Default to FilesystemCoordination
        """
        if self.backend == CoordinationBackend.AGENTMEMORY and self.agentmemory_enabled:
            try:
                return AgentMemoryCoordination(self.agentmemory_url)
            except (ConnectionError, NotImplementedError) as e:
                if self.fallback_enabled:
                    import logging
                    logging.warning(
                        f"agentmemory unavailable, falling back to filesystem: {e}"
                    )
                    return FilesystemCoordination()
                raise

        return FilesystemCoordination()
