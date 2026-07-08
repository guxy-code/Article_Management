"""
Agent 工具模块
将论文管理功能封装为 LangChain Tool，供 Agent 调用。
"""

import os
from langchain_core.tools import tool

from parsers import get_parser
from parsers.metadata_extractor import MetadataExtractor
from store.text_splitter import split_text
from store.vector_store import VectorStore
from rag.qa_chain import PaperQAChain


# 全局实例（在 main.py 中初始化后注入）
_vector_store: VectorStore | None = None
_qa_chain: PaperQAChain | None = None
_metadata_extractor: MetadataExtractor | None = None


def init_tools(vector_store: VectorStore, qa_chain: PaperQAChain):
    """初始化工具所需的全局依赖"""
    global _vector_store, _qa_chain, _metadata_extractor
    _vector_store = vector_store
    _qa_chain = qa_chain
    _metadata_extractor = MetadataExtractor()


@tool
def add_paper(pdf_path: str, title: str = "") -> str:
    """上传一篇 PDF 论文到知识库。解析 PDF 内容，切分后存入向量数据库。
    参数：
        pdf_path: PDF 文件的完整路径
        title: 论文标题（可选，留空则自动识别）
    """
    if _vector_store is None:
        return "❌ 系统未初始化"

    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        return f"❌ 文件不存在: {pdf_path}"

    # 解析 PDF
    try:
        parser = get_parser("pypdf")
        result = parser.parse(pdf_path)
    except Exception as e:
        return f"❌ PDF 解析失败: {e}"

    # 确定标题：优先用用户指定的，否则用 LLM 从第一页提取
    if title.strip():
        paper_title = title.strip()
        paper_authors = result.authors or "unknown"
    else:
        # 用 LLM 提取标题和作者
        first_page = result.pages[0] if result.pages else result.text[:2000]
        metadata = _metadata_extractor.extract(first_page)
        paper_title = metadata["title"] or os.path.basename(pdf_path)
        paper_authors = metadata["authors"] or "unknown"

    # 检查是否已入库
    if _vector_store.has_paper(paper_title):
        return f"⚠️ 论文《{paper_title}》已经在知识库中，无需重复上传。"

    # 切分文本
    chunks = split_text(result.text, chunk_size=800, chunk_overlap=100)

    if not chunks:
        return "❌ 论文内容为空，无法入库。"

    # 入库
    count = _vector_store.add_paper(
        chunks=chunks,
        title=paper_title,
        authors=paper_authors,
        source_path=pdf_path,
    )

    return f"✅ 已入库: 《{paper_title}》，共 {count} 个片段。"


@tool
def ask_paper(question: str) -> str:
    """根据已入库的论文内容回答问题。使用语义检索找到相关片段，然后生成回答。
    参数：
        question: 你想问的问题，比如"这篇论文的创新点是什么"、"双信号控制的原理"
    """
    if _qa_chain is None:
        return "❌ 系统未初始化"

    if not question.strip():
        return "❌ 请输入一个问题。"

    result = _qa_chain.ask_with_sources(question.strip(), k=5)

    answer = result["answer"]
    sources = result["sources"]

    if sources:
        source_info = "\n📖 来源: " + ", ".join(
            [f"《{s['title']}》" for s in sources]
        )
        # 去重
        source_info = "\n📖 来源: " + ", ".join(
            sorted(set([f"《{s['title']}》" for s in sources]))
        )
        return answer + source_info

    return answer


@tool
def search_papers(query: str) -> str:
    """在知识库中语义检索，返回最相关的论文片段（不经过 LLM 生成）。
    适合想看原文片段的场景。
    参数：
        query: 搜索内容，如"对比学习方法"、"通信效率优化"
    """
    if _vector_store is None:
        return "❌ 系统未初始化"

    docs = _vector_store.search(query.strip(), k=5)

    if not docs:
        return "📭 未找到相关内容。知识库可能为空，请先上传论文。"

    lines = [f"📖 找到 {len(docs)} 段相关内容：\n"]
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("title", "未知")
        lines.append(f"--- 片段 {i} (来源: 《{title}》) ---")
        lines.append(doc.page_content[:300])
        lines.append("")

    return "\n".join(lines)


@tool
def list_papers() -> str:
    """列出知识库中所有已上传的论文。"""
    if _vector_store is None:
        return "❌ 系统未初始化"

    papers = _vector_store.list_papers()

    if not papers:
        return "📭 知识库为空，还没有上传任何论文。"

    lines = [f"📚 已入库 {len(papers)} 篇论文："]
    for i, title in enumerate(papers, 1):
        lines.append(f"  {i}. 《{title}》")

    lines.append(f"\n📊 向量库共 {_vector_store.total_chunks} 个片段")
    return "\n".join(lines)


@tool
def delete_paper(title: str) -> str:
    """从知识库中删除一篇论文。
    参数：
        title: 要删除的论文标题（需要和入库时一致）
    """
    if _vector_store is None:
        return "❌ 系统未初始化"

    if not title.strip():
        return "❌ 请提供论文标题。"

    success = _vector_store.delete_paper(title.strip())

    if success:
        return f"✅ 已删除: 《{title.strip()}》"
    else:
        return f"❌ 未找到论文《{title.strip()}》，请检查标题是否正确。可用 list_papers 查看已有论文。"
