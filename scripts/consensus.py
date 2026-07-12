#!/usr/bin/env python3
"""共识检测模块 - 简化版MVP"""

from typing import Dict, Tuple
from difflib import SequenceMatcher


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两段文本的相似度"""
    return SequenceMatcher(None, text1, text2).ratio()


def detect_consensus(responses: Dict[str, str], threshold: float = 0.7) -> Tuple[bool, float]:
    """检测agents是否达成共识"""
    if len(responses) < 2:
        return False, 0.0

    agents = list(responses.keys())
    similarities = []

    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            sim = calculate_similarity(responses[agents[i]], responses[agents[j]])
            similarities.append(sim)

    avg_similarity = sum(similarities) / len(similarities)
    return avg_similarity >= threshold, avg_similarity
