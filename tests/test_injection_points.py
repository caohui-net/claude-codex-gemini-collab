#!/usr/bin/env python3
"""验证注入点在collab_discuss中的集成"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from collab_skills_utils import generate_doubt_driven_prompt, generate_spec_driven_prd

def test_doubt_driven_call():
    """验证doubt-driven函数可正常调用"""
    print("\n[1/3] 验证doubt-driven函数调用")

    result = generate_doubt_driven_prompt(
        topic="选择消息队列方案",
        dissent="性能争议",
        blocking_issues=["缺少benchmark", "成本未评估"]
    )

    assert result, "应返回提示内容"
    assert "blocking" in result.lower(), "应包含blocking关键词"
    assert "2" in result, "应包含issues数量"
    print(f"✓ doubt-driven返回 {len(result)} 字符")

def test_spec_driven_call():
    """验证spec-driven函数可正常调用"""
    print("\n[2/3] 验证spec-driven函数调用")

    result = generate_spec_driven_prd(
        topic="选择消息队列方案",
        consensus_detail={
            "decision": "使用Kafka作为主消息队列",
            "evidence": ["高吞吐量测试通过", "社区活跃"],
            "action_items": ["搭建集群", "编写SDK"]
        },
        artifacts=["DISCUSS-mq-choice.md"]
    )

    assert result, "应返回PRD内容"
    assert "## 决策" in result, "应包含决策章节"
    assert "Kafka" in result, "应包含决策内容"
    print(f"✓ spec-driven返回 {len(result)} 字符")

def test_imports_work():
    """验证collab_discuss中的导入不会报错"""
    print("\n[3/3] 验证collab_discuss导入")

    try:
        # 这会执行顶层导入，但不会运行main
        import collab_discuss
        print("✓ collab_discuss导入成功")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        raise

if __name__ == "__main__":
    print("=== 注入点集成验证 ===")

    try:
        test_doubt_driven_call()
        test_spec_driven_call()
        test_imports_work()
        print("\n=== 所有验证通过 ✓ ===")
    except AssertionError as e:
        print(f"\n❌ 验证失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
