#!/usr/bin/env python3
"""
AsyncHub - Hub的异步接口封装

为Hub提供asyncio兼容的异步操作接口，支持并发访问。
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from hub import Hub, HubSnapshot


class AsyncHub:
    """Hub的异步包装器"""

    def __init__(self, base_dir: Path):
        """初始化AsyncHub

        Args:
            base_dir: 项目根目录
        """
        self.hub = Hub(base_dir)
        self._lock = asyncio.Lock()

    async def create_snapshot(self, agent: str, content: str,
                             metadata: Optional[Dict[str, Any]] = None) -> HubSnapshot:
        """异步创建快照"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.hub.create_snapshot, agent, content, metadata
        )

    async def get_snapshot(self, snapshot_id: str) -> Optional[HubSnapshot]:
        """异步获取快照"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.hub.get_snapshot, snapshot_id
        )

    async def list_snapshots(self, agent: Optional[str] = None) -> List[HubSnapshot]:
        """异步列出快照"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.hub.list_snapshots, agent
        )

    async def update_current(self, agent: str, snapshot: HubSnapshot) -> None:
        """异步更新current symlink"""
        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.hub.update_current, agent, snapshot
            )

    async def get_current_snapshot(self, agent: str) -> Optional[HubSnapshot]:
        """异步获取当前快照"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.hub.get_current_snapshot, agent
        )
