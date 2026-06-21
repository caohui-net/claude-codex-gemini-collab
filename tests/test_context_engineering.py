#!/usr/bin/env python3
"""P1测试：Context Engineering - 跨agent上下文共享"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from collab_context_engineering import extract_key_points, build_shared_context, inject_context_to_prompt

def test_extract_key_points():
    """测试关键点提取"""
    print("\n[1/3] 测试关键点提取")

    responses = [
        {
            "agent": "codex",
            "decision": "使用Kafka作为消息队列",
            "evidence": ["高吞吐量", "社区活跃"],
            "blocking_issues": ["成本未评估"]
        },
        {
            "agent": "gemini",
            "decision": "建议RabbitMQ",
            "evidence": ["易于部署"],
            "blocking_issues": []
        }
    ]

    points = extract_key_points(responses)

    assert len(points) > 0, "应提取到关键点"
    assert any("codex" in p for p in points), "应包含codex的发现"
    assert any("成本" in p or "blocking" in p.lower() for p in points), "应包含blocking问题"

    print(f"✓ 提取到 {len(points)} 个关键点")

def test_build_shared_context():
    """测试共享上下文构建"""
    print("\n[2/3] 测试共享上下文构建")

    responses = [
        {
            "agent": "codex",
            "decision": "方案A",
            "blocking_issues": ["问题X"]
        }
    ]

    # 轮次1不应生成上下文
    ctx1 = build_shared_context(1, responses)
    assert ctx1 == "", "轮次1不应生成上下文"

    # 轮次2应生成上下文
    ctx2 = build_shared_context(2, responses)
    assert ctx2 != "", "轮次2应生成上下文"
    assert "关键发现" in ctx2, "应包含标题"
    assert "codex" in ctx2, "应包含agent名称"

    print(f"✓ 共享上下文生成正确 ({len(ctx2)}字符)")

def test_inject_context():
    """测试上下文注入"""
    print("\n[3/3] 测试上下文注入")

    base_prompt = "请分析这个方案"
    context = "📋 前序发现:\n  • 关键点1"

    injected = inject_context_to_prompt(base_prompt, context)

    assert "前序发现" in injected, "应包含上下文"
    assert "请分析" in injected, "应保留原始prompt"
    assert injected.index("前序发现") < injected.index("请分析"), "上下文应在prompt前"

    print("✓ 上下文注入正确")

if __name__ == "__main__":
    print("=== P1: Context Engineering 测试 ===")

    try:
        test_extract_key_points()
        test_build_shared_context()
        test_inject_context()
        print("\n=== P1测试通过 ✓ ===")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
