#!/usr/bin/env python3
"""Hub功能测试"""

import sys
import tempfile
from pathlib import Path

# 添加scripts到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from hub import Hub, HubSnapshot


def test_create_snapshot():
    """测试创建快照"""
    with tempfile.TemporaryDirectory() as tmpdir:
        hub = Hub(Path(tmpdir))

        snapshot = hub.create_snapshot(
            agent="codex",
            content="test content",
            metadata={"elapsed_sec": 1.5}
        )

        assert snapshot.agent == "codex"
        assert snapshot.content == "test content"
        assert snapshot.metadata["elapsed_sec"] == 1.5
        print("✓ test_create_snapshot passed")


def test_get_snapshot():
    """测试读取快照"""
    with tempfile.TemporaryDirectory() as tmpdir:
        hub = Hub(Path(tmpdir))

        # 创建快照
        snapshot1 = hub.create_snapshot("gemini", "test")

        # 读取快照
        snapshot2 = hub.get_snapshot(snapshot1.snapshot_id)

        assert snapshot2 is not None
        assert snapshot2.snapshot_id == snapshot1.snapshot_id
        assert snapshot2.content == "test"
        print("✓ test_get_snapshot passed")


def test_list_snapshots():
    """测试列出快照"""
    with tempfile.TemporaryDirectory() as tmpdir:
        hub = Hub(Path(tmpdir))

        # 创建多个快照
        hub.create_snapshot("codex", "content1")
        hub.create_snapshot("gemini", "content2")
        hub.create_snapshot("claude", "content3")

        # 列出所有快照
        all_snapshots = hub.list_snapshots()
        assert len(all_snapshots) == 3

        # 列出特定agent的快照
        codex_snapshots = hub.list_snapshots(agent="codex")
        assert len(codex_snapshots) == 1
        assert codex_snapshots[0].agent == "codex"
        print("✓ test_list_snapshots passed")
