#!/usr/bin/env python3
"""RAG文档检索工具"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rag import SimpleRAG


def build_index(doc_dir: str) -> SimpleRAG:
    """构建文档索引"""
    rag = SimpleRAG()
    doc_path = Path(doc_dir)

    # 索引所有markdown文档
    for md_file in doc_path.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            rag.add_document(str(md_file.relative_to(doc_path)), content)
        except Exception as e:
            print(f"⚠️  跳过 {md_file}: {e}", file=sys.stderr)

    return rag


def main():
    if len(sys.argv) < 3:
        print("用法: rag_search.py <文档目录> <查询>")
        sys.exit(1)

    doc_dir = sys.argv[1]
    query = " ".join(sys.argv[2:])

    print(f"📚 构建索引: {doc_dir}")
    rag = build_index(doc_dir)
    print(f"✅ 已索引 {len(rag.documents)} 个文档")

    print(f"\n🔍 检索: {query}")
    results = rag.search(query, top_k=3)

    print("\n📊 检索结果:")
    for i, (doc_id, score) in enumerate(results, 1):
        print(f"{i}. {doc_id} (相似度: {score:.3f})")


if __name__ == "__main__":
    main()
