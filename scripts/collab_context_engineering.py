"""Agent-Skills P1: Context Engineering - 跨agent上下文共享"""

def extract_key_points(responses):
    """从agent响应中提取关键点"""
    if not responses:
        return []

    key_points = []
    for resp in responses:
        agent = resp.get('agent', 'unknown')
        decision = resp.get('decision', '')
        blocking = resp.get('blocking_issues', [])
        evidence = resp.get('evidence', [])

        # 提取核心主张
        if decision:
            key_points.append(f"[{agent}] {decision[:100]}")

        # 提取关键证据
        if evidence:
            key_points.append(f"[{agent}] 证据: {', '.join(evidence[:2])}")

        # 提取blocking问题
        if blocking:
            key_points.append(f"[{agent}] ⚠️ {', '.join(blocking[:2])}")

    return key_points


def build_shared_context(round_num, responses, max_points=5):
    """构建跨agent共享上下文"""
    if round_num <= 1 or not responses:
        return ""

    key_points = extract_key_points(responses)
    if not key_points:
        return ""

    # 限制上下文大小
    selected = key_points[:max_points]

    context = f"""📋 前序agent关键发现（轮次{round_num-1}）:
{chr(10).join(f'  • {point}' for point in selected)}
"""
    return context


def inject_context_to_prompt(base_prompt, shared_context):
    """将共享上下文注入到agent提示中"""
    if not shared_context:
        return base_prompt

    return f"""{shared_context}

---
{base_prompt}"""
