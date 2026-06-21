"""Agent-Skills P2: Incremental Implementation - 任务分解与排序"""

def extract_dependencies(action_items):
    """从action_items中提取依赖关系"""
    if not action_items:
        return []

    # 中英文关键词映射（优先级：数字越小越先执行）
    dependency_keywords = {
        # Phase 0: 基础设施
        "setup": 0, "init": 0, "初始化": 0,
        "install": 0, "安装": 0, "依赖": 0,
        # Phase 1: 配置
        "config": 1, "配置": 1,
        # Phase 2: 实现
        "implement": 2, "实现": 2, "开发": 2, "添加": 2,
        # Phase 3: 测试
        "test": 3, "测试": 3, "验证": 3,
        # Phase 4: 文档
        "doc": 4, "文档": 4, "documentation": 4,
        # Phase 5: 部署
        "deploy": 5, "部署": 5, "上线": 5
    }

    scored = []
    for idx, item in enumerate(action_items):
        item_text = str(item).lower()

        # 计算优先级分数（越小越先）
        score = 999
        for keyword, priority in dependency_keywords.items():
            if keyword in item_text:
                score = min(score, priority)

        scored.append({
            "task": item,
            "priority": score,
            "original_index": idx
        })

    return sorted(scored, key=lambda x: (x["priority"], x["original_index"]))


def generate_implementation_plan(action_items, decision):
    """生成增量实施计划"""
    if not action_items:
        return ""

    ordered = extract_dependencies(action_items)

    # 按优先级分组
    phases = {}
    for item in ordered:
        priority = item["priority"]
        if priority not in phases:
            phases[priority] = []
        phases[priority].append(item["task"])

    # 生成计划
    phase_names = {
        0: "Phase 1: 基础设施",
        1: "Phase 2: 配置",
        2: "Phase 3: 实现",
        3: "Phase 4: 验证",
        4: "Phase 5: 文档",
        5: "Phase 6: 部署"
    }

    plan = f"""## 增量实施计划

**决策：** {decision[:100]}...

"""

    for priority in sorted(phases.keys()):
        phase_name = phase_names.get(priority, f"Phase {priority+1}")
        tasks = phases[priority]

        plan += f"""### {phase_name}
{chr(10).join(f'- [ ] {task}' for task in tasks)}

"""

    plan += """### 实施建议
- 按phase顺序执行
- 每完成一个phase验证后再继续
- 遇到blocking及时回退讨论
"""

    return plan
