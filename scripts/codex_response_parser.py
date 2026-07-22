#!/usr/bin/env python3
"""
Codex响应解析器 - 将结构化Markdown转换为JSON

解决问题：当Codex无法直接返回JSON时，通过固定的Markdown格式保证一致性
"""

import re
import json
from typing import Dict, List, Any, Optional


class CodexResponseParser:
    """解析Codex的结构化Markdown响应"""

    def __init__(self):
        self.sections = {
            'summary': r'###?\s*(?:概述|Summary|摘要)[：:]\s*(.+?)(?=###|$)',
            'issues': r'###?\s*(?:问题|Issues|潜在问题)[：:]?\s*\n((?:[-*]\s*.+\n?)+)',
            'recommendations': r'###?\s*(?:建议|Recommendations|改进建议)[：:]?\s*\n((?:[-*]\s*.+\n?)+)',
            'complexity': r'###?\s*(?:复杂度|Complexity)[：:]\s*(.+?)(?=###|$)',
        }

    def parse(self, text: str) -> Dict[str, Any]:
        """解析结构化文本为JSON"""
        result = {}

        # 提取各个section
        for key, pattern in self.sections.items():
            match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
            if match:
                content = match.group(1).strip()

                # 处理列表项
                if key in ['issues', 'recommendations']:
                    items = re.findall(r'[-*]\s*(.+)', content)
                    result[key] = [item.strip() for item in items if item.strip()]
                else:
                    result[key] = content

        return result

    def extract_severity(self, issue_text: str) -> str:
        """从问题描述中提取严重程度"""
        text_lower = issue_text.lower()
        if any(word in text_lower for word in ['critical', '严重', '致命', 'high']):
            return 'high'
        elif any(word in text_lower for word in ['medium', '中等', 'moderate']):
            return 'medium'
        else:
            return 'low'

    def parse_with_severity(self, text: str) -> Dict[str, Any]:
        """解析并提取问题的严重程度"""
        result = self.parse(text)

        # 增强issues字段，提取severity
        if 'issues' in result:
            enhanced_issues = []
            for issue in result['issues']:
                enhanced_issues.append({
                    'description': issue,
                    'severity': self.extract_severity(issue)
                })
            result['issues'] = enhanced_issues

        return result


def create_structured_prompt(task: str) -> str:
    """生成要求结构化输出的prompt"""
    return f"""{task}

请按以下格式输出：

### 概述
[简要说明]

### 问题
- [问题1]
- [问题2]

### 建议
- [建议1]
- [建议2]

### 复杂度
[low/medium/high]"""


# 测试示例
if __name__ == "__main__":
    # 模拟Codex返回的结构化文本
    sample_response = """
### 概述
该文件实现了并行执行引擎，使用asyncio并发运行多个agents。

### 问题
- 缺少对None files参数的显式检查（中等严重）
- run_agent_async中的错误处理不够完善
- 没有超时重试机制（严重）

### 建议
- 添加参数验证逻辑
- 增强异常处理和日志记录
- 实现指数退避重试策略

### 复杂度
medium
"""

    parser = CodexResponseParser()

    # 基础解析
    result = parser.parse(sample_response)
    print("基础解析结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n" + "="*60 + "\n")

    # 增强解析（包含severity）
    enhanced = parser.parse_with_severity(sample_response)
    print("增强解析结果:")
    print(json.dumps(enhanced, ensure_ascii=False, indent=2))

    print("\n" + "="*60 + "\n")

    # 生成结构化prompt示例
    prompt = create_structured_prompt("审查这个文件的代码质量")
    print("结构化Prompt示例:")
    print(prompt)
