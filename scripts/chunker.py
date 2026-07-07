#!/usr/bin/env python3
"""
Markdown Chunker - 递归分块策略
移除5KB文件大小限制，支持任意大小markdown

版本：简化版（基于字符数，可升级到tiktoken版本）
"""
from typing import List, Optional


class MarkdownChunker:
    """
    Markdown递归分块器

    策略：
    1. 优先按markdown结构分块（## 标题, ### 子标题）
    2. 次优按段落分块（\n\n）
    3. 最后按句子/空格分块
    4. 添加150字符重叠区域

    Note: 当前使用字符数近似token数（1 token ≈ 3-4字符）
          可升级为tiktoken版本以精确控制token数
    """

    # 分隔符优先级（从高到低）
    SEPARATORS = [
        '\n\n## ',      # H2标题
        '\n\n### ',     # H3标题
        '\n\n#### ',    # H4标题
        '\n\n',         # 段落
        '\n',           # 换行
        '. ',           # 句子
        ' '             # 单词
    ]

    def __init__(self, max_chars: int = 8000, overlap_chars: int = 600):
        """
        初始化分块器

        Args:
            max_chars: 每块最大字符数（≈2000 tokens）
            overlap_chars: 重叠字符数（≈150 tokens）
        """
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str) -> List[str]:
        """
        分块markdown文本

        Args:
            text: markdown文本

        Returns:
            分块后的文本列表
        """
        if not text:
            return []

        # 如果文本小于max_chars，直接返回
        if len(text) <= self.max_chars:
            return [text]

        # 递归分块
        chunks = self._recursive_split(text, 0)

        # 添加重叠区域
        return self._add_overlap(chunks)

    def _recursive_split(self, text: str, sep_idx: int) -> List[str]:
        """
        递归分割文本

        Args:
            text: 待分割文本
            sep_idx: 当前分隔符索引

        Returns:
            分割后的文本块列表
        """
        # 如果文本足够小，直接返回
        if len(text) <= self.max_chars:
            return [text]

        # 如果已经用完所有分隔符，强制截断
        if sep_idx >= len(self.SEPARATORS):
            return self._hard_split(text)

        # 使用当前分隔符分割
        sep = self.SEPARATORS[sep_idx]
        parts = text.split(sep)

        chunks = []
        current_chunk = ""

        for i, part in enumerate(parts):
            # 重新添加分隔符（除了第一个part）
            if i > 0:
                test_chunk = current_chunk + sep + part
            else:
                test_chunk = part

            # 如果加上这个part后仍然小于max_chars
            if len(test_chunk) <= self.max_chars:
                current_chunk = test_chunk
            else:
                # 保存当前chunk
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果part本身太大，递归分割
                if len(part) > self.max_chars:
                    sub_chunks = self._recursive_split(part, sep_idx + 1)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        # 添加最后一个chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _hard_split(self, text: str) -> List[str]:
        """
        强制截断文本（当所有分隔符都失败时）

        Args:
            text: 待截断文本

        Returns:
            截断后的文本块列表
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.max_chars
            chunk = text[start:end]
            chunks.append(chunk)
            start = end

        return chunks

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """
        在chunk之间添加重叠区域

        Args:
            chunks: 原始chunk列表

        Returns:
            添加重叠后的chunk列表
        """
        if len(chunks) <= 1:
            return chunks

        overlapped = []

        for i, chunk in enumerate(chunks):
            if i > 0:
                # 从前一个chunk取尾部overlap_chars字符
                prev_tail = chunks[i-1][-self.overlap_chars:]
                chunk = prev_tail + chunk

            overlapped.append(chunk)

        return overlapped

    def chunk_with_metadata(self, text: str, filename: str = "") -> List[dict]:
        """
        分块并添加元数据

        Args:
            text: markdown文本
            filename: 文件名

        Returns:
            包含元数据的chunk列表
        """
        chunks = self.chunk(text)

        return [
            {
                "content": chunk,
                "metadata": {
                    "filename": filename,
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "char_count": len(chunk)
                }
            }
            for i, chunk in enumerate(chunks)
        ]


def estimate_tokens(text: str) -> int:
    """
    估算文本token数（基于字符数）

    近似公式：1 token ≈ 4字符（英文）, 1 token ≈ 2字符（中文）
    保守估计：1 token ≈ 3字符

    Args:
        text: 文本

    Returns:
        估算的token数
    """
    return len(text) // 3


if __name__ == "__main__":
    # 测试用例
    chunker = MarkdownChunker(max_chars=100, overlap_chars=20)

    test_text = """# Title

## Section 1

This is a long paragraph that needs to be split into multiple chunks for better processing.

## Section 2

Another section with more content. This should demonstrate the chunking strategy.

### Subsection 2.1

Even more detailed content here."""

    chunks = chunker.chunk(test_text)

    print(f"原文长度: {len(test_text)}字符")
    print(f"分块数量: {len(chunks)}")
    print(f"估算tokens: {estimate_tokens(test_text)}")
    print("\n分块结果:")

    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i}/{len(chunks)} ({len(chunk)}字符) ---")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)

    # 测试带元数据
    print("\n\n=== 带元数据测试 ===")
    chunks_with_meta = chunker.chunk_with_metadata(test_text, "test.md")
    for item in chunks_with_meta:
        print(f"\nChunk {item['metadata']['chunk_index']}/{item['metadata']['total_chunks']}")
        print(f"字符数: {item['metadata']['char_count']}")
