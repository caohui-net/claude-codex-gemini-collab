#!/usr/bin/env python3
"""
LangGraph工作流编排
实现混合并行（fan-out + pipeline）+ 异步执行
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, List, Optional
import asyncio
import json
import time
from pathlib import Path
from functools import wraps
from audit_logger import AuditLogger
from consensus import check_consensus

# 初始化审计日志
_audit_logger = AuditLogger()


def async_retry(max_attempts: int = 3, base_delay: float = 2.0):
    """异步重试装饰器（指数退避）"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️  重试 {attempt + 1}/{max_attempts}，等待{delay}s...")
                    await asyncio.sleep(delay)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class CollabState(TypedDict):
    """协作状态"""
    prompt: str
    documents: List[str]
    codex_result: Optional[str]
    gemini_result: Optional[str]
    claude_result: Optional[str]
    final_report: Optional[str]
    error: Optional[str]


@async_retry(max_attempts=3, base_delay=2.0)
async def run_agent(agent_name: str, prompt: str, docs: List[str] = None) -> str:
    """异步调用单个agent（带重试+审计）"""
    start_time = time.time()
    error = None
    result = None

    cmd = ["python3", "scripts/agent_cli.py", agent_name, prompt]
    if docs:
        for doc in docs:
            cmd.extend(["--file", doc])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode == 0:
            result = stdout.decode('utf-8')
            return result
        else:
            error = f"Agent failed: {stderr.decode('utf-8')}"
            raise RuntimeError(error)
    except asyncio.TimeoutError as e:
        error = f"Agent {agent_name} timeout"
        raise TimeoutError(error)
    except Exception as e:
        error = f"Agent {agent_name} error: {str(e)}"
        raise RuntimeError(error)
    finally:
        duration = time.time() - start_time
        _audit_logger.log(agent_name, prompt, result, duration, error)


async def codex_node(state: CollabState) -> dict:
    """Codex节点（异步）"""
    result = await run_agent("codex", state["prompt"], state.get("documents"))
    return {"codex_result": result}


async def gemini_node(state: CollabState) -> dict:
    """Gemini节点（异步）"""
    result = await run_agent("gemini", state["prompt"], state.get("documents"))
    return {"gemini_result": result}


async def claude_node(state: CollabState) -> dict:
    """Claude节点（异步）"""
    result = await run_agent("claude", state["prompt"], state.get("documents"))
    return {"claude_result": result}


async def synthesize_node(state: CollabState) -> dict:
    """综合节点（异步）+ 共识判定"""
    results = [
        state.get('codex_result', ''),
        state.get('gemini_result', ''),
        state.get('claude_result', '')
    ]

    # 检查共识
    consensus = check_consensus(results, threshold=0.7)

    synthesis_prompt = f"""请综合以下三个AI的分析结果：

**Codex分析**:
{state.get('codex_result', 'N/A')}

**Gemini分析**:
{state.get('gemini_result', 'N/A')}

**Claude分析**:
{state.get('claude_result', 'N/A')}

**共识分析**:
- 平均相似度: {consensus['average_similarity']}
- 是否达成共识: {'是' if consensus['has_consensus'] else '否'}

请给出综合报告。"""

    # 使用claude做综合（因为它最擅长综合）
    final_report = await run_agent("claude", synthesis_prompt)
    return {"final_report": final_report}


async def start_node(state: CollabState) -> dict:
    """启动节点（fan-out入口，异步）"""
    return state


def create_workflow(use_checkpointer: bool = False) -> StateGraph:
    """创建工作流图（fan-out并行 + 异步执行）"""
    # 创建StateGraph
    workflow = StateGraph(CollabState)

    # 添加节点
    workflow.add_node("start", start_node)
    workflow.add_node("codex", codex_node)
    workflow.add_node("gemini", gemini_node)
    workflow.add_node("claude", claude_node)
    workflow.add_node("synthesize", synthesize_node)

    # Fan-out: start → 3个agent并行
    workflow.set_entry_point("start")
    workflow.add_edge("start", "codex")
    workflow.add_edge("start", "gemini")
    workflow.add_edge("start", "claude")

    # 汇总: 3个agent → synthesize
    workflow.add_edge("codex", "synthesize")
    workflow.add_edge("gemini", "synthesize")
    workflow.add_edge("claude", "synthesize")

    # 结束
    workflow.add_edge("synthesize", END)

    # 编译图（暂时不使用checkpointer）
    app = workflow.compile(checkpointer=None)

    return app


async def run_collaboration(prompt: str, documents: List[str] = None) -> dict:
    """运行协作工作流（异步）"""
    app = create_workflow()

    # 初始状态
    initial_state: CollabState = {
        "prompt": prompt,
        "documents": documents or [],
        "codex_result": None,
        "gemini_result": None,
        "claude_result": None,
        "final_report": None,
        "error": None
    }

    # 异步执行工作流
    config = {"configurable": {"thread_id": "collab-1"}}
    result = await app.ainvoke(initial_state, config)

    return result


if __name__ == "__main__":
    # 测试（异步）
    async def main():
        result = await run_collaboration(
            prompt="分析Python的优缺点",
            documents=[]
        )
        print("Final Report:")
        print(result.get("final_report"))

    asyncio.run(main())
