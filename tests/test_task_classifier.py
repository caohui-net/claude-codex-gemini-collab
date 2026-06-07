#!/usr/bin/env python3
"""Tests for task classifier."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ccg_collab.scripts.task_classifier import classify_task, route_to_agents


def test_ui_task_classification():
    """Test UI task identification."""
    result = classify_task("修复登录按钮样式", ["src/components/Login.tsx"])
    assert result.task_type == "ui"
    assert result.confidence >= 0.85
    assert "ui_design" in result.required_capabilities
    print(f"✓ UI task: {result.task_type} (confidence: {result.confidence:.2f})")


def test_code_task_classification():
    """Test code task identification."""
    result = classify_task("优化API查询逻辑", ["src/api/query.py"])
    assert result.task_type == "code"
    assert result.confidence >= 0.80
    assert "code_review" in result.required_capabilities
    print(f"✓ Code task: {result.task_type} (confidence: {result.confidence:.2f})")


def test_audit_task_classification():
    """Test audit task identification."""
    result = classify_task("审查代码质量并验证测试覆盖率")
    assert result.task_type == "audit"
    assert result.confidence >= 0.90
    assert "audit" in result.required_capabilities
    print(f"✓ Audit task: {result.task_type} (confidence: {result.confidence:.2f})")


def test_reasoning_task_classification():
    """Test reasoning task identification."""
    result = classify_task("分析用户体验改进方案并权衡技术架构")
    assert result.task_type == "reasoning"
    assert result.confidence >= 0.75
    assert "reasoning" in result.required_capabilities
    print(f"✓ Reasoning task: {result.task_type} (confidence: {result.confidence:.2f})")


def test_discussion_task_classification():
    """Test discussion task identification."""
    result = classify_task("讨论数据表格组件实现方案")
    assert result.task_type in ["discussion", "mixed"]
    print(f"✓ Discussion task: {result.task_type} (confidence: {result.confidence:.2f})")


def test_routing():
    """Test agent routing."""
    # UI -> Gemini (with file path for clear classification)
    ui_result = classify_task("修改按钮样式和布局", ["src/components/Button.css"])
    agents = route_to_agents(ui_result)
    assert agents == ["gemini"]
    print(f"✓ UI routing: {agents}")

    # Code -> Codex
    code_result = classify_task("实现API接口逻辑", ["src/api/service.py"])
    agents = route_to_agents(code_result)
    assert agents == ["codex"]
    print(f"✓ Code routing: {agents}")

    # Reasoning -> Claude
    reasoning_result = classify_task("分析架构方案并权衡设计决策")
    agents = route_to_agents(reasoning_result)
    assert agents == ["claude"]
    print(f"✓ Reasoning routing: {agents}")

    # Discussion -> All
    discussion_result = classify_task("讨论技术选型和方案评估")
    agents = route_to_agents(discussion_result)
    assert "claude" in agents and "codex" in agents
    print(f"✓ Discussion routing: {agents}")


if __name__ == "__main__":
    print("Testing task classifier...")
    test_ui_task_classification()
    test_code_task_classification()
    test_audit_task_classification()
    test_reasoning_task_classification()
    test_discussion_task_classification()
    test_routing()
    print("\n✓ All tests passed!")
