#!/usr/bin/env python3
"""共识判定机制"""
from difflib import SequenceMatcher
from typing import List, Dict, Tuple


def text_similarity(text1: str, text2: str) -> float:
    """计算两段文本的相似度（0-1）"""
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1, text2).ratio()


def check_consensus(results: List[str], threshold: float = 0.7) -> Dict:
    """
    检查多个结果的共识

    Args:
        results: agent结果列表
        threshold: 相似度阈值（0-1）

    Returns:
        {
            "has_consensus": bool,
            "similarity_matrix": [[float]],
            "average_similarity": float,
            "majority_result": str
        }
    """
    n = len(results)
    if n < 2:
        return {
            "has_consensus": True,
            "similarity_matrix": [[1.0]],
            "average_similarity": 1.0,
            "majority_result": results[0] if results else ""
        }

    # 计算相似度矩阵
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                sim = text_similarity(results[i], results[j])
                row.append(sim)
        matrix.append(row)

    # 计算平均相似度
    total_sim = sum(sum(row) for row in matrix) - n  # 减去对角线
    avg_sim = total_sim / (n * (n - 1)) if n > 1 else 1.0

    # 判定共识
    has_consensus = avg_sim >= threshold

    # 选择多数结果（最相似的那个）
    avg_sims = [sum(row) / n for row in matrix]
    majority_idx = avg_sims.index(max(avg_sims))

    return {
        "has_consensus": has_consensus,
        "similarity_matrix": matrix,
        "average_similarity": round(avg_sim, 3),
        "majority_result": results[majority_idx]
    }
