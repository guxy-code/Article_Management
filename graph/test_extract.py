"""
测试知识图谱提取 + Neo4j 存储完整流程
用法：python graph/test_extract.py <pdf路径>
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from parsers import get_parser
from graph.extractor import KnowledgeExtractor
from graph.neo4j_store import GraphStore


def main():
    if len(sys.argv) < 2:
        print("用法: python graph/test_extract.py <pdf路径>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🧠 知识图谱提取测试")
    print("=" * 60)

    # Step 1: 解析 PDF
    print("\n🔹 Step 1: 解析 PDF")
    parser = get_parser("pypdf")
    result = parser.parse(pdf_path)
    print(f"  ✅ 解析完成: {len(result.text)} 字符")

    # Step 2: LLM 提取三元组
    print("\n🔹 Step 2: LLM 提取知识三元组")
    extractor = KnowledgeExtractor()

    # 用前 3000 字符（摘要+方法）
    first_pages = result.pages[0] if result.pages else result.text[:3000]
    title = result.title or os.path.basename(pdf_path)

    # 用 metadata_extractor 获取更准确的标题
    from parsers.metadata_extractor import MetadataExtractor
    meta_ext = MetadataExtractor()
    metadata = meta_ext.extract(first_pages)
    title = metadata["title"] or title
    authors = metadata["authors"] or "unknown"

    print(f"  📄 标题: {title}")
    print(f"  ✍️  作者: {authors}")
    print(f"  ⏳ 正在提取...")

    graph_data = extractor.extract(result.text[:3000], title=title, authors=authors)

    print(f"  ✅ 提取完成！")
    print(f"\n  📊 提取结果:")
    print(f"    Methods: {len(graph_data.get('methods', []))}")
    for m in graph_data.get("methods", []):
        print(f"      • {m['name']}: {m.get('description', '')}")
    print(f"    Problems: {len(graph_data.get('problems', []))}")
    for p in graph_data.get("problems", []):
        print(f"      • {p['name']}: {p.get('description', '')}")
    print(f"    Concepts: {graph_data.get('concepts', [])}")
    print(f"    Datasets: {graph_data.get('datasets', [])}")
    print(f"    Relations: {len(graph_data.get('relations', []))}")
    for r in graph_data.get("relations", []):
        print(f"      • {r['from']} --[{r['type']}]--> {r['to']}")

    # Step 3: 存入 Neo4j
    print(f"\n🔹 Step 3: 存入 Neo4j")
    store = GraphStore()
    store.init_schema()
    store.add_paper_graph(graph_data)
    print(f"  ✅ 已写入 Neo4j！")

    # 验证
    stats = store.get_stats()
    print(f"\n  📊 图谱统计:")
    for label, count in stats["nodes"].items():
        print(f"    {label}: {count}")
    print(f"    总关系数: {stats['total_edges']}")

    store.close()
    print(f"\n🎉 完成！打开 http://localhost:7474 可以在 Neo4j Browser 中查看图谱。")


if __name__ == "__main__":
    main()
