#!/usr/bin/env python3
"""
LangGraph工作流编排
实现混合并行（fan-out + pipeline）
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, List, Optional
import subprocess
import json
from pathlib import Path


class CollabState(TypedDict):
    """协作状态"""
    prompt: str
    documents: List[str]
    codex_result: Optional[str]
    gemini_result: Optional[str]
    claude_result: Optional[str]
    final_report: Optional[str]
    error: Optional[str]


def run_agent(agent_name: str, prompt: str, docs: List[str] = None) -> str:
    """调用单个agent"""
    cmd = ["python3", "scripts/agent_cli.py", agent_name, prompt]
    if docs:
        for doc in docs:
            cmd.extend(["--file", doc])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Timeout"
    except Exception as e:
        return f"Error: {str(e)}"


def codex_node(state: CollabState) -> dict:
    """Codex节点"""
    result = run_agent("codex", state["prompt"], state.get("documents"))
    return {"codex_result": result}


def gemini_node(state: CollabState) -> dict:
    """Gemini节点"""
    result = run_agent("gemini", state["prompt"], state.get("documents"))
    return {"gemini_result": result}


def claude_node(state: CollabState) -> dict:
    """Claude节点"""
    result = run_agent("claude", state["prompt"], state.get("documents"))
    return {"claude_result": result}


def synthesize_node(state: CollabState) -> dict:
    """综合节点"""
    synthesis_prompt = f"""请综合以下三个AI的分析结果：

**Codex分析**:
{state.get('codex_result', 'N/A')}

**Gemini分析**:
{state.get('gemini_result', 'N/A')}

**Claude分析**:
{state.get('claude_result', 'N/A')}

请给出综合报告。"""

    # 使用claude做综合（因为它最擅长综合）
    final_report = run_agent("claude", synthesis_prompt)
    return {"final_report": final_report}


def start_node(state: CollabState) -> dict:
    """启动节点（fan-out入口）"""
    return state


def create_workflow(use_checkpointer: bool = False) -> StateGraph:
    """创建工作流图（fan-out并行）"""
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


def run_collaboration(prompt: str, documents: List[str] = None) -> dict:
    """运行协作工作流"""
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

    # 执行工作流
    config = {"configurable": {"thread_id": "collab-1"}}
    result = app.invoke(initial_state, config)

    return result


if __name__ == "__main__":
    # 测试
    result = run_collaboration(
        prompt="分析Python的优缺点",
        documents=[]
    )
    print("Final Report:")
    print(result.get("final_report"))
