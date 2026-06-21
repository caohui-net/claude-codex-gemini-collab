"""
Agent Response Validator
基于 Fable 5 安全原则验证 agent 响应
"""
import re
from typing import Dict, List, Tuple

DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    (r"rm\s+-rf\s+/", "危险删除"),
    (r"chmod\s+777", "不安全权限"),
    (r"eval\s*\(", "代码注入"),
    (r"exec\s*\(", "代码执行"),
    (r"__import__\s*\(", "动态导入"),
]

CITATION_MAX_WORDS = 15


def validate_response(response: Dict, agent: str) -> Dict:
    """
    验证 agent 响应，应用安全边界

    Args:
        response: agent 原始响应
        agent: agent 名称

    Returns:
        验证后的响应（可能被拦截）
    """
    content = response.get("content", "")

    # 1. 危险命令检测
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return {
                "agent": agent,
                "consensus": False,
                "blocking_issues": [f"安全风险: {desc}"],
                "content": "[已拦截: 违反安全策略]"
            }

    # 2. 引用长度检测
    quotes = re.findall(r'["""](.*?)["""]', content, re.DOTALL)
    for quote in quotes:
        word_count = len(quote.split())
        if word_count > CITATION_MAX_WORDS:
            issues = response.get("blocking_issues", [])
            issues.append(
                f"引用过长: {word_count} 词 (限制 {CITATION_MAX_WORDS})"
            )
            response["blocking_issues"] = issues

    return response
