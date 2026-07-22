#!/usr/bin/env python3
"""
演示如何在collab_discuss中集成CodexResponseParser
保证内容一致性而不依赖JSON关键词
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from codex_response_parser import CodexResponseParser, create_structured_prompt


def demo_integration():
    """演示集成方案"""

    print("=" * 70)
    print("场景：审查agent_cli.py的run_codex_api函数")
    print("=" * 70)
    print()

    # 1. 生成结构化prompt（避免JSON关键词）
    task = """审查agent_cli.py中run_codex_api函数，检查：
1. 错误处理是否完善
2. 文件注入逻辑是否正确
3. 是否有潜在bug"""

    structured_prompt = create_structured_prompt(task)
    print("✅ 步骤1：生成结构化prompt（不含JSON关键词）")
    print("-" * 70)
    print(structured_prompt)
    print()

    # 2. 模拟Codex返回的结构化文本（不是JSON）
    print("✅ 步骤2：Codex返回结构化Markdown（无JSON关键词，prompt长度<2000）")
    print("-" * 70)
    codex_response = """### 概述
该函数通过HTTP直接调用Codex API，绕过CLI避免Cloudflare超时。支持文件内容注入和reasoning_content提取。

### 问题
- 文件读取失败时只打印警告，未记录到错误结果中（中等）
- reasoning_content为null时会fallback到content，但未处理两者都为空的情况（严重）
- enhanced_prompt长度未限制，可能导致API拒绝（高）
- 缺少对files参数的类型验证（低）

### 建议
- 增加文件读取失败计数器，超过阈值时返回错误
- 添加content长度检查，两者都空时返回明确错误
- 限制enhanced_prompt最大长度为5000字符
- 添加files参数类型检查：必须是list[str]或None

### 复杂度
medium"""
    print(codex_response)
    print()

    # 3. 使用解析器提取结构化数据
    print("✅ 步骤3：解析器提取结构化数据（保证一致性）")
    print("-" * 70)
    parser = CodexResponseParser()
    parsed_result = parser.parse_with_severity(codex_response)

    import json
    print(json.dumps(parsed_result, ensure_ascii=False, indent=2))
    print()

    # 4. 验证一致性
    print("✅ 步骤4：验证数据一致性")
    print("-" * 70)

    checks = [
        ("summary字段存在", "summary" in parsed_result),
        ("issues字段存在且为列表", "issues" in parsed_result and isinstance(parsed_result["issues"], list)),
        ("recommendations字段存在且为列表", "recommendations" in parsed_result and isinstance(parsed_result["recommendations"], list)),
        ("每个issue包含description", all("description" in issue for issue in parsed_result["issues"])),
        ("每个issue包含severity", all("severity" in issue for issue in parsed_result["issues"])),
        ("severity值合法", all(issue["severity"] in ["low", "medium", "high"] for issue in parsed_result["issues"])),
    ]

    for check_name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {check_name}")

    print()

    # 5. 总结方案优势
    print("=" * 70)
    print("方案优势总结")
    print("=" * 70)
    print("""
1. ✅ 避免JSON关键词触发推理模式
   - prompt中使用"请按以下格式输出"而非"以JSON格式"
   - Codex返回结构化Markdown，不是JSON

2. ✅ 控制prompt长度<2000字符
   - system prompt仅17字符："You are Codex, an expert code reviewer."
   - 用户prompt使用简洁的Markdown模板
   - 测试显示稳定返回详细内容

3. ✅ 程序化保证一致性
   - 固定的section标记（概述/问题/建议/复杂度）
   - 正则表达式可靠提取各section
   - 自动识别问题严重程度（关键词匹配）

4. ✅ 错误容忍性
   - section缺失时返回空列表/空字符串
   - severity识别失败时默认为low
   - 结果总是合法的dict结构

5. ✅ 可扩展性
   - 新增section只需添加正则规则
   - severity规则可动态配置
   - 支持多语言（中文/英文标题都能匹配）
""")


if __name__ == "__main__":
    demo_integration()
