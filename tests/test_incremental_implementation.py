#!/usr/bin/env python3
"""P2测试：Incremental Implementation - 任务分解与排序"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from collab_incremental_implementation import extract_dependencies, generate_implementation_plan

def test_extract_dependencies():
    """测试依赖提取和排序"""
    print("\n[1/2] 测试任务排序")

    action_items = [
        "编写单元测试",
        "安装依赖包",
        "实现核心功能",
        "部署到生产环境",
        "配置环境变量"
    ]

    ordered = extract_dependencies(action_items)

    assert len(ordered) == 5, "应保留所有任务"

    # 验证顺序：install < config < implement < test < deploy
    order_check = [item["task"] for item in ordered]
    install_idx = next(i for i, t in enumerate(order_check) if "安装" in t)
    config_idx = next(i for i, t in enumerate(order_check) if "配置" in t)
    impl_idx = next(i for i, t in enumerate(order_check) if "实现" in t)
    test_idx = next(i for i, t in enumerate(order_check) if "测试" in t)
    deploy_idx = next(i for i, t in enumerate(order_check) if "部署" in t)

    assert install_idx < impl_idx, "安装应在实现之前"
    assert config_idx < impl_idx, "配置应在实现之前"
    assert impl_idx < test_idx, "实现应在测试之前"
    assert test_idx < deploy_idx, "测试应在部署之前"

    print(f"✓ 任务排序正确：{' → '.join(order_check)}")

def test_generate_implementation_plan():
    """测试实施计划生成"""
    print("\n[2/2] 测试实施计划生成")

    action_items = [
        "编写API文档",
        "实现JWT中间件",
        "配置Redis连接",
        "安装PyJWT依赖"
    ]
    decision = "使用JWT进行认证"

    plan = generate_implementation_plan(action_items, decision)

    assert plan, "应生成实施计划"
    assert "Phase" in plan, "应包含阶段划分"
    assert "JWT" in plan, "应包含决策内容"
    assert "安装" in plan, "应包含安装任务"
    assert all(item in plan for item in action_items), "应包含所有action_items"

    print(f"✓ 实施计划生成成功 ({len(plan)}字符)")

if __name__ == "__main__":
    print("=== P2: Incremental Implementation 测试 ===")

    try:
        test_extract_dependencies()
        test_generate_implementation_plan()
        print("\n=== P2测试通过 ✓ ===")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
