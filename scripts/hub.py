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

    def get_snapshot(self, snapshot_id: str) -> Optional[HubSnapshot]:
        """读取指定快照

        Args:
            snapshot_id: 快照ID

        Returns:
            HubSnapshot对象，如果不存在返回None
        """
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return None

        with open(snapshot_file, 'r', encoding='utf-8') as f:
            return HubSnapshot.from_json(f.read())

    def list_snapshots(self, agent: Optional[str] = None) -> List[HubSnapshot]:
        """列出所有快照

        Args:
            agent: 可选，仅返回指定agent的快照

        Returns:
            HubSnapshot列表，按时间戳降序排序
        """
        snapshots = []
        for snapshot_file in self.snapshots_dir.glob("*.json"):
            try:
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    snapshot = HubSnapshot.from_json(f.read())
                    if agent is None or snapshot.agent == agent:
                        snapshots.append(snapshot)
            except Exception:
                continue  # 跳过损坏的快照文件

        # 按时间戳降序排序
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        return snapshots

    def update_current(self, agent: str, snapshot: HubSnapshot) -> None:
        """原子更新current symlink指向最新快照

        使用临时symlink + rename实现原子性，确保并发安全

        Args:
            agent: agent名称
            snapshot: 要设置为current的快照
        """
        target = self.snapshots_dir / f"{snapshot.snapshot_id}.json"
        link_path = self.current_dir / f"{agent}.json"
        temp_link = self.current_dir / f".{agent}.json.tmp"

        # 删除可能存在的临时文件
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()

        # 创建临时symlink
        os.symlink(target, temp_link)

        # 原子替换（rename是原子操作）
        temp_link.replace(link_path)

    def get_current_snapshot(self, agent: str) -> Optional[HubSnapshot]:
        """获取agent的当前快照

        Args:
            agent: agent名称

        Returns:
            当前快照，如果不存在返回None
        """
        link_path = self.current_dir / f"{agent}.json"
        if not link_path.exists():
            return None

        try:
            with open(link_path, 'r', encoding='utf-8') as f:
                return HubSnapshot.from_json(f.read())
        except Exception:
            return None
