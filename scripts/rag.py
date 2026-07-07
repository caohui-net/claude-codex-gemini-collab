#!/usr/bin/env python3
"""简单的向量检索（RAG）模块 - 基于TF-IDF"""
from pathlib import Path
from typing import List, Tuple
import json
import re


class SimpleRAG:
    """简单的TF-IDF向量检索"""

    def __init__(self, cache_path: str = ".collab/rag_cache.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.documents = []
        self.vectors = []

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        text = text.lower()
        tokens = re.findall(r'\w+', text)
        return tokens

    def _compute_tf(self, tokens: List[str]) -> dict:
        """计算词频"""
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        # 归一化
        total = len(tokens)
        if total > 0:
            for token in tf:
                tf[token] = tf[token] / total
        return tf

    def add_document(self, doc_id: str, content: str):
        """添加文档"""
        tokens = self._tokenize(content)
        tf = self._compute_tf(tokens)
        self.documents.append({"id": doc_id, "content": content})
        self.vectors.append(tf)

    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """检索相关文档"""
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)

        scores = []
        for i, doc_vector in enumerate(self.vectors):
            # 计算cosine相似度（简化版）
            score = 0.0
            for token, freq in query_tf.items():
                if token in doc_vector:
                    score += freq * doc_vector[token]
            scores.append((self.documents[i]["id"], score))

        # 排序返回top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def save_cache(self):
        """保存缓存"""
        cache_data = {
            "documents": self.documents,
            "vectors": self.vectors
        }
        with self.cache_path.open("w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def load_cache(self):
        """加载缓存"""
        if self.cache_path.exists():
            with self.cache_path.open("r", encoding="utf-8") as f:
                cache_data = json.load(f)
                self.documents = cache_data.get("documents", [])
                self.vectors = cache_data.get("vectors", [])
