#!/usr/bin/env python3
"""Parallel mode handler for collab_discuss"""

import asyncio
import time
from pathlib import Path
from typing import List

from parallel_engine import parallel_run_agents


def run_parallel_discussion(topic: str, participants: List[str],
                           base_dir: Path, timeout_sec: int = 180) -> int:
    """运行parallel模式discussion

    Args:
        topic: 讨论主题
        participants: 参与的agents列表
        base_dir: 项目根目录
        timeout_sec: 每个agent的超时时间

    Returns:
        退出码（0=成功）
    """
    print("🚀 [Parallel Mode] Async parallel execution")
    print(f"💬 Topic: {topic}")
    print(f"👥 Participants: {', '.join(participants)}")

    discussion_start = time.time()

    # 运行并行执行
    try:
        results = asyncio.run(parallel_run_agents(participants, topic, base_dir, timeout_sec))

        # 输出结果
        print("\n" + "="*60)
        for agent, reply in results.items():
            print(f"\n[{agent}] ({reply.elapsed_sec:.1f}s)")
            print("-" * 40)
            print(reply.raw_text[:500])  # 显示前500字符
            if len(reply.raw_text) > 500:
                print(f"... ({len(reply.raw_text)} chars total)")

        discussion_elapsed = time.time() - discussion_start
        print(f"\n⏱️  Total: {discussion_elapsed:.1f}s")
        print(f"✅ Parallel execution complete. {len(results)} agents ran concurrently.")

        return 0

    except Exception as e:
        print(f"\n❌ Error in parallel execution: {e}")
        return 1
