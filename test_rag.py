"""
测试完整 RAG 流程：解析 PDF → 切分 → 入库 → 检索问答
用法：python test_rag.py <pdf文件路径>
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import get_parser
from store.text_splitter import split_text
from store.vector_store import VectorStore
from rag.qa_chain import PaperQAChain


def main():
    if len(sys.argv) < 2:
        print("用法: python test_rag.py <pdf文件路径>")
        print("示例: python test_rag.py article/your_paper.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("📚 论文 RAG 全流程测试")
    print("=" * 60)

    # === Step 1: 解析 PDF ===
    print("\n🔹 Step 1: 解析 PDF")
    parser = get_parser("pypdf")
    result = parser.parse(pdf_path)
    print(f"  ✅ 解析完成: {len(result.text)} 字符, {result.total_pages} 页")
    print(f"  📄 标题: {result.title or '未识别'}")

    # === Step 2: 文本切分 ===
    print("\n🔹 Step 2: 文本切分")
    chunks = split_text(result.text, chunk_size=800, chunk_overlap=100)
    print(f"  ✅ 切分完成: {len(chunks)} 个 chunk")
    print(f"  📏 chunk 示例 (第1个): {chunks[0][:100]}...")

    # === Step 3: 向量入库 ===
    print("\n🔹 Step 3: 向量入库 (embedding + Chroma)")

    # 手动设置标题（因为 pypdf 的标题识别不太准）
    title = input("  ✏️  请输入论文标题 (回车跳过，用自动识别): ").strip()
    if not title:
        title = result.title or os.path.basename(pdf_path)

    store = VectorStore()
    count = store.add_paper(
        chunks=chunks,
        title=title,
        source_path=pdf_path,
    )
    print(f"  ✅ 入库完成: {count} 个 chunk 已存入向量库")
    print(f"  📊 向量库总量: {store.total_chunks} 个 chunk")
    print(f"  📚 已入库论文: {store.list_papers()}")

    # === Step 4: 检索问答 ===
    print("\n🔹 Step 4: RAG 检索问答")
    print("  输入问题测试检索效果 (输入 'quit' 退出)")

    qa = PaperQAChain(vector_store=store)

    while True:
        question = input("\n  👤 你的问题: ").strip()
        if question.lower() in ["quit", "exit", "q", "退出"]:
            break
        if not question:
            continue

        print("  ⏳ 检索 + 生成中...")
        result = qa.ask_with_sources(question, k=3)

        print(f"\n  🤖 回答:")
        print(f"  {result['answer']}")

        if result["sources"]:
            print(f"\n  📖 来源:")
            for s in result["sources"]:
                print(f"    - [{s['title']}] chunk#{s['chunk_index']}")

    print("\n✅ 测试结束！")


if __name__ == "__main__":
    main()
