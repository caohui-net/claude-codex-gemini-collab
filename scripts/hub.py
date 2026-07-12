#!/usr/bin/env python3
"""
Hub - 协作中心架构

实现不可变快照机制和原子symlink更新，支持无锁并发访问。
灵感来自MassGen项目的Hub架构。

核心概念:
- 不可变快照: 每个agent的输出保存为独立的快照文件
- 原子更新: 使用symlink的原子性保证并发安全
- 版本化存储: 快照按时间戳和agent名称组织
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class HubSnapshot:
    """不可变快照数据结构"""
    agent: str  # agent名称 (codex, gemini, claude)
    timestamp: float  # Unix时间戳
    content: str  # agent输出内容
    metadata: Dict[str, Any]  # 元数据（elapsed_sec, tokens等）
    snapshot_id: str  # 唯一标识符

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'HubSnapshot':
        """从字典创建"""
        return cls(**data)

    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'HubSnapshot':
        """从JSON反序列化"""
        return cls.from_dict(json.loads(json_str))


class Hub:
    """协作Hub - 管理agent快照和并发访问"""

    def __init__(self, base_dir: Path):
        """初始化Hub

        Args:
            base_dir: 项目根目录，Hub数据存储在 {base_dir}/.collab/hub/
        """
        self.base_dir = Path(base_dir)
        self.hub_dir = self.base_dir / ".collab" / "hub"
        self.snapshots_dir = self.hub_dir / "snapshots"
        self.current_dir = self.hub_dir / "current"
        self.metadata_dir = self.hub_dir / "metadata"

        # 确保目录存在
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, agent: str, content: str,
                       metadata: Optional[Dict[str, Any]] = None) -> HubSnapshot:
        """创建新的不可变快照

        Args:
            agent: agent名称 (codex, gemini, claude)
            content: agent输出内容
            metadata: 可选的元数据

        Returns:
            创建的HubSnapshot对象
        """
        timestamp = time.time()
        snapshot_id = f"{agent}_{int(timestamp * 1000)}"

        snapshot = HubSnapshot(
            agent=agent,
            timestamp=timestamp,
            content=content,
            metadata=metadata or {},
            snapshot_id=snapshot_id
        )

        # 保存快照到文件
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            f.write(snapshot.to_json())

        return snapshot
