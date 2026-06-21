#!/usr/bin/env python3
"""端到端测试：验证agent-skills在协作流程中的完整集成"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from collab_skills import generate_doubt_driven_prompt, generate_spec_driven_prd

def test_doubt_driven_injection():
    """测试doubt-driven在轮次失败后的注入"""
    print("\n[E2E-1] 测试doubt-driven注入点")

    # 模拟轮次失败场景
    topic = "实现JWT认证中间件"
    dissent = "Codex建议使用jose库，Gemini担心性能问题"
    blocking = ["性能基准未明确", "错误处理策略缺失"]

    result = generate_doubt_driven_prompt(topic, dissent, blocking)

    # 验证生成的提示
    assert result is not None, "应该生成doubt-driven提示"
    assert len(result) > 0, "提示不应为空"
    assert "性能" in result or "错误" in result, "应包含blocking关键词"

    print(f"✓ doubt-driven提示生成成功 ({len(result)}字符)")
    print(f"  预览: {result[:100]}...")

def test_spec_driven_injection():
    """测试spec-driven在共识达成后的注入"""
    print("\n[E2E-2] 测试spec-driven注入点")

    # 模拟共识达成场景
    topic = "实现JWT认证中间件"
    consensus_detail = {
        "consensus": True,
        "decision": "使用PyJWT库，添加token刷新机制",
        "evidence": ["PyJWT性能测试通过", "支持RS256算法"],
        "action_items": ["编写中间件", "添加单元测试", "更新文档"]
    }
    artifacts = ["DISCUSS-jwt-auth-consensus.md"]

    result = generate_spec_driven_prd(topic, consensus_detail, artifacts)

    # 验证生成的PRD
    assert result is not None, "应该生成spec-driven PRD"
    assert "## 决策" in result or "## 行动项" in result, "应包含PRD结构"
    assert "PyJWT" in result, "应包含技术决策"

    print(f"✓ spec-driven PRD生成成功 ({len(result)}字符)")
    print(f"  包含章节: {result.count('##')}个")

def test_full_workflow():
    """测试完整工作流：失败→doubt-driven→成功→spec-driven"""
    print("\n[E2E-3] 测试完整工作流")

    topic = "数据库迁移方案"

    # Step 1: 第一轮失败→生成doubt-driven
    print("  [1/3] 轮次1失败，生成doubt-driven...")
    doubt1 = generate_doubt_driven_prompt(
        topic,
        "版本冲突",
        ["回滚策略未定义"]
    )
    assert doubt1, "第一轮应生成doubt-driven提示"

    # Step 2: 第二轮失败→再次生成doubt-driven
    print("  [2/3] 轮次2失败，生成doubt-driven...")
    doubt2 = generate_doubt_driven_prompt(
        topic,
        "性能担忧",
        ["数据量评估缺失"]
    )
    assert doubt2, "第二轮应生成doubt-driven提示"

    # Step 3: 第三轮成功→生成spec-driven
    print("  [3/3] 轮次3成功，生成spec-driven...")
    prd = generate_spec_driven_prd(
        topic,
        {
            "consensus": True,
            "decision": "使用Alembic进行增量迁移",
            "action_items": ["编写迁移脚本", "验证回滚"]
        },
        []
    )
    assert prd, "共识达成应生成spec-driven PRD"
    assert "Alembic" in prd, "PRD应包含决策内容"

    print("✓ 完整工作流测试通过")

if __name__ == "__main__":
    print("=== Agent-Skills端到端集成测试 ===")

    try:
        test_doubt_driven_injection()
        test_spec_driven_injection()
        test_full_workflow()
        print("\n=== 所有E2E测试通过 ✓ ===")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
