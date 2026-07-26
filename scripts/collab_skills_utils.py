"""Agent-skills集成工具函数"""

def inject_doubt_driven_hint(blocking_issues):
    """简化版doubt-driven提示生成（仅blocking_issues）"""
    if not blocking_issues:
        return ""

    return f"""[Doubt-Driven审查建议]
发现 {len(blocking_issues)} 个blocking_issues:
{', '.join(blocking_issues[:3])}
建议应用对抗性审查流程。"""

def generate_prd_from_consensus(decision, evidence, action_items):
    """基于共识参数生成PRD（简化版）"""
    prd = f"""# PRD: 协作决策

## 决策
{decision}

## 证据
{chr(10).join(f'- {e}' for e in evidence)}

## 行动项
{chr(10).join(f'- owner: {item["owner"]}, task: {item["task"]}' for item in action_items)}
"""
    return prd

def generate_doubt_driven_prompt(topic, dissent, blocking_issues):
    """生成doubt-driven提示：针对blocking问题提供引导性问题"""
    if not blocking_issues:
        return ""

    return f"""💭 Doubt-Driven审查建议:
当前轮次发现 {len(blocking_issues)} 个blocking问题，建议应用对抗性审查：
1. CLAIM: 从issues中提取主张
2. EXTRACT: 隔离最小可审查单元
3. DOUBT: 生成反证问题（为什么这个主张可能错？）
4. RECONCILE: 分类发现
5. STOP: 检查是否可停止

Issues: {', '.join(blocking_issues[:3])}
"""

def generate_spec_driven_prd(topic, consensus_detail, artifacts):
    """基于共识生成spec-driven PRD"""
    decision = consensus_detail.get('decision', '')
    evidence = consensus_detail.get('evidence', [])
    action_items = consensus_detail.get('action_items', [])

    prd = f"""# PRD: {topic}

## 决策
{decision}

## 证据
{chr(10).join(f'- {e}' for e in evidence[:5])}

## 行动项
{chr(10).join(f'- {item}' for item in action_items[:5])}

## 验收标准
- [ ] 所有行动项完成
- [ ] 证据充分支持决策
- [ ] 无未解决的blocking问题

## 参考artifacts
{chr(10).join(f'- {a}' for a in artifacts)}
"""
    return prd
