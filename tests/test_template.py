#!/usr/bin/env python3
"""测试Jinja2模板渲染"""
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# 加载模板
template_dir = Path(".collab/templates")
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("context.j2")

print("=== Jinja2模板测试 ===\n")

# 测试1: 单chunk场景
print("--- 测试1: 单chunk ---")
rendered1 = template.render(
    prompt="请分析这个文档",
    filename="test.md",
    filepath="docs/test.md",
    chunks=["# Title\n\nThis is a test document."]
)
print(rendered1)
print()

# 测试2: 多chunk场景（第1块）
print("\n--- 测试2: 多chunk（第1块）---")
rendered2 = template.render(
    prompt="请分析这个文档",
    filename="large.md",
    filepath="docs/large.md",
    chunks=["Chunk 1 content", "Chunk 2 content", "Chunk 3 content"],
    current_chunk=1,
    total_chunks=3
)
print(rendered2)
print()

# 测试3: 多chunk场景（第2块）
print("\n--- 测试3: 多chunk（第2块）---")
rendered3 = template.render(
    prompt="请分析这个文档",
    filename="large.md",
    filepath="docs/large.md",
    chunks=["Chunk 1 content", "Chunk 2 content", "Chunk 3 content"],
    current_chunk=2,
    total_chunks=3
)
print(rendered3)

print("\n✅ 模板渲染测试完成")
