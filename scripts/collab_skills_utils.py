"""Agent-skills集成工具函数 - 最小化版本"""

def inject_doubt_driven_hint(blocking_issues):
    """在有blocking_issues时返回doubt-driven提示"""
    if not blocking_issues:
        return ""

    return f"""
[Doubt-Driven审查提示]
当前轮次发现 {len(blocking_issues)} 个blocking_issues，建议应用对抗性审查：
1. CLAIM: 从issues中提取主张
2. EXTRACT: 隔离最小可审查单元
3. DOUBT: 生成反证问题（为什么这个主张可能错？）
4. RECONCILE: 分类发现
5. STOP: 检查是否可停止

Issues: {', '.join(blocking_issues[:3])}
"""

def generate_prd_from_consensus(decision, evidence, action_items):
    """基于共识生成简化PRD"""
    prd = f"""# PRD: {decision[:50]}...

## 决策
{decision}

## 证据
{chr(10).join(f'- {e}' for e in evidence[:5])}

## 行动项
{chr(10).join(f'- [{item.get("owner", "未分配")}] {item.get("task", "")}' for item in action_items[:5])}

## 验收标准
- [ ] 所有行动项完成
- [ ] 证据充分支持决策
- [ ] 无未解决的blocking_issues
"""
    return prd
