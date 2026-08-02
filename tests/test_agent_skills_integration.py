#!/usr/bin/env python3
"""Agent-skills P0集成测试"""
import sys
sys.path.insert(0, 'scripts')

from collab_skills import load_skill_prompt, topic_is_vague
from collab_skills_utils import generate_doubt_driven_prompt, generate_spec_driven_prd

def test_interview_me():
    """测试interview-me技能加载"""
    prompt = load_skill_prompt("interview-me")
    assert prompt, "interview-me加载失败"
    assert len(prompt) > 50, "interview-me内容过短"
    print("✓ interview-me加载成功")

def test_topic_vague_detection():
    """测试模糊topic检测"""
    cases = [
        ("优化系统", True),
        ("整合agent-skills", True),
        ("修复src/auth/login.py第42行的空指针异常", False),
        ("实现JWT认证中间件支持refresh token和blacklist", False),
    ]

    for topic, expected in cases:
        result = topic_is_vague(topic)
        status = "✓" if result == expected else "✗"
        print(f"{status} topic_is_vague('{topic[:30]}...'): {result} (期望: {expected})")

def test_doubt_driven():
    """测试doubt-driven提示生成"""
    hint = generate_doubt_driven_prompt("测试topic", "dissent", ["未明确X边界", "假设Y未验证"])
    assert "Doubt-Driven" in hint, "提示格式错误"
    assert "2 个blocking问题" in hint, "issues计数错误"
    print("✓ doubt-driven提示生成成功")

    # 空issues应返回空字符串
    empty = generate_doubt_driven_prompt("测试topic", "dissent", [])
    assert empty == "", "空issues应返回空字符串"
    print("✓ doubt-driven空降级正确")

def test_spec_driven():
    """测试spec-driven PRD生成"""
    consensus_detail = {
        "decision": "P0技能作为阶段增强集成",
        "evidence": ["Codex r3证据", "兼容性合同"],
        "action_items": [
            {"owner": "claude", "task": "创建技能加载器"},
            {"owner": "codex", "task": "审查集成点"},
        ]
    }
    prd = generate_spec_driven_prd(
        "测试topic",
        consensus_detail,
        ["artifact1.md", "artifact2.md"]
    )

    assert "# PRD:" in prd, "PRD标题缺失"
    assert "## 决策" in prd, "决策section缺失"
    assert "## 证据" in prd, "证据section缺失"
    assert "## 行动项" in prd, "行动项section缺失"
    print("✓ spec-driven PRD生成成功")

if __name__ == "__main__":
    print("=== Agent-Skills P0集成测试 ===\n")

    print("[1/4] 测试interview-me技能加载")
    test_interview_me()

    print("\n[2/4] 测试模糊topic检测")
    test_topic_vague_detection()

    print("\n[3/4] 测试doubt-driven提示")
    test_doubt_driven()

    print("\n[4/4] 测试spec-driven PRD生成")
    test_spec_driven()

    print("\n=== 所有测试通过 ✓ ===")
