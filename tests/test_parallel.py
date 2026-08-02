#!/usr/bin/env python3
"""并行执行引擎测试"""

import sys
import asyncio
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from async_hub import AsyncHub
from hub import HubSnapshot


@pytest.mark.asyncio
async def test_async_hub():
    """测试AsyncHub基础功能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        hub = AsyncHub(Path(tmpdir))

        # 测试异步创建快照
        snapshot = await hub.create_snapshot("codex", "test content")
        assert snapshot.agent == "codex"

        # 测试异步读取
        retrieved = await hub.get_snapshot(snapshot.snapshot_id)
        assert retrieved.content == "test content"

        print("✓ AsyncHub basic operations work")


if __name__ == "__main__":
    print("=== Parallel Engine Tests ===")
    asyncio.run(test_async_hub())
    print("✅ All parallel tests passed!")
