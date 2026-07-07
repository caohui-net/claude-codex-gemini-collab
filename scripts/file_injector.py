#!/usr/bin/env python3
"""
文件注入Helper - 使用Chunker和Jinja2模板
"""
from pathlib import Path
from typing import List, Tuple
from jinja2 import Environment, FileSystemLoader
import sys

# 添加scripts目录到path
sys.path.insert(0, str(Path(__file__).parent))
from chunker import MarkdownChunker


def inject_files(prompt: str, base_dir: Path, files: List[str]) -> Tuple[str, bool]:
    """
    注入文件内容到prompt，支持任意大小文件

    Args:
        prompt: 原始prompt
        base_dir: 基础目录
        files: 文件列表

    Returns:
        (injected_prompt, needs_multi_turn):
        - injected_prompt: 注入文件后的prompt
        - needs_multi_turn: 是否需要多轮处理（文件太大被分块）
    """
    if not files:
        return prompt, False

    # 加载Jinja2模板
    template_dir = Path(__file__).parent.parent / ".collab" / "templates"
    if not template_dir.exists():
        # Fallback: 简单拼接
        return _fallback_inject(prompt, base_dir, files)

    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        template = env.get_template("context.j2")
    except:
        return _fallback_inject(prompt, base_dir, files)

    # 处理第一个文件（多文件支持留待后续）
    file_path = base_dir / files[0]
    if not file_path.exists():
        return prompt, False

    # 读取并分块
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    chunker = MarkdownChunker(max_chars=8000, overlap_chars=600)
    chunks = chunker.chunk(content)

    # 使用模板渲染
    if len(chunks) == 1:
        # 单chunk：直接注入
        injected = template.render(
            prompt=prompt,
            filename=file_path.name,
            filepath=str(files[0]),
            chunks=chunks
        )
        return injected, False
    else:
        # 多chunk：返回第一块，标记需要多轮
        injected = template.render(
            prompt=prompt,
            filename=file_path.name,
            filepath=str(files[0]),
            chunks=chunks,
            current_chunk=1,
            total_chunks=len(chunks)
        )
        return injected, True


def _fallback_inject(prompt: str, base_dir: Path, files: List[str]) -> Tuple[str, bool]:
    """Fallback: 简单文件注入（无模板）"""
    injected = []
    for f in files:
        file_path = base_dir / f
        if not file_path.exists():
            continue

        # 移除5KB限制
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        injected.append(f"<file path='{f}'>\n{content}\n</file>")

    if injected:
        return "\n".join(injected) + "\n\n" + prompt, False

    return prompt, False


if __name__ == "__main__":
    # 测试
    from pathlib import Path
    test_prompt = "请分析这个文档"
    test_dir = Path("/home/caohui/projects/claude-codex-gemini-collab/docs")
    test_files = ["multi-agent-implementation-plan-final.md"]

    result, multi_turn = inject_files(test_prompt, test_dir, test_files)
    print(f"需要多轮: {multi_turn}")
    print(f"结果长度: {len(result)}字符")
    print(f"前200字符:\n{result[:200]}...")
