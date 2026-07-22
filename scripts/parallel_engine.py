#!/usr/bin/env python3
"""
并行执行引擎 - 使用asyncio并行运行多个agents

基于Hub架构，每个agent写入独立快照，无竞态条件。
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from async_hub import AsyncHub
from agent_cli import run_codex, run_gemini, run_claude, AgentReply


async def run_agent_async(agent_name: str, prompt: str, hub: AsyncHub,
                         base_dir: Path, timeout_sec: int = 180) -> AgentReply:
    """异步运行单个agent并保存到Hub

    Args:
        agent_name: agent名称
        prompt: 提示词
        hub: AsyncHub实例
        base_dir: 项目根目录
        timeout_sec: 超时时间

    Returns:
        AgentReply对象
    """
    loop = asyncio.get_event_loop()

    # 在executor中运行同步agent函数
    if agent_name == "codex":
        reply = await loop.run_in_executor(None, run_codex, prompt, base_dir, None, timeout_sec)
    elif agent_name == "gemini":
        reply = await loop.run_in_executor(None, run_gemini, prompt, base_dir, None, timeout_sec)
    elif agent_name == "claude":
        reply = await loop.run_in_executor(None, run_claude, prompt, base_dir, None, timeout_sec)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")

    # 保存到Hub快照
    metadata = {
        "elapsed_sec": reply.elapsed_sec,
        "exit_code": reply.exit_code
    }
    await hub.create_snapshot(agent_name, reply.raw_text, metadata)

    return reply


async def parallel_run_agents(agents: List[str], prompt: str, base_dir: Path,
                              timeout_sec: int = 180) -> Dict[str, AgentReply]:
    """并行运行多个agents

    Args:
        agents: agent名称列表
        prompt: 提示词
        base_dir: 项目根目录
        timeout_sec: 超时时间

    Returns:
        {agent_name: AgentReply} 字典
    """
    hub = AsyncHub(base_dir)

    # 创建并行任务
    tasks = [
        run_agent_async(agent, prompt, hub, base_dir, timeout_sec)
        for agent in agents
    ]

    # 并行执行
    replies = await asyncio.gather(*tasks, return_exceptions=True)

    # 构建结果字典
    results = {}
    for agent, reply in zip(agents, replies):
        if isinstance(reply, Exception):
            print(f"Error running {agent}: {reply}")
            continue
        results[agent] = reply

    return results
