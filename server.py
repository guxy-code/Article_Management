"""
📚 PaperMind - FastAPI 后端 API
提供论文管理、RAG 问答、会话管理、语义检索的 HTTP 接口。

启动方式：uvicorn server:app --reload --port 8000
API 文档：http://localhost:8000/docs
"""

import os
import sys
import json
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parsers import get_parser
from parsers.metadata_extractor import MetadataExtractor
from store.text_splitter import split_text
from store.vector_store import VectorStore
from store.bm25_store import BM25Store
from store.hybrid_retriever import HybridRetriever
from store.reranker import LLMReranker
from rag.qa_chain import PaperQAChain
from rag.session_store import SessionStore
from graph.neo4j_store import GraphStore
from graph.extractor import KnowledgeExtractor


# ========== 初始化 ==========

app = FastAPI(
    title="PaperMind API",
    description="AI Research Workspace - 论文管理与智能问答",
    version="2.0.0",
)

# CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
vector_store = VectorStore()
session_store = SessionStore()

# 构建 BM25 索引（从 Chroma 加载已有文档）
bm25_store = BM25Store()
try:
    all_docs = vector_store.get_all_documents()
    if all_docs:
        bm25_store.build_index(all_docs)
except Exception as e:
    print(f"⚠️ BM25 索引构建跳过: {e}")
    all_docs = []

# LLM 重排序器
reranker = LLMReranker()

# 混合检索器
hybrid_retriever = HybridRetriever(
    vector_store=vector_store,
    bm25_store=bm25_store,
    reranker=reranker,
)

qa_chain = PaperQAChain(
    vector_store=vector_store,
    hybrid_retriever=hybrid_retriever,
    session_store=session_store,
)
metadata_extractor = MetadataExtractor()

# 知识图谱
graph_store = GraphStore()
graph_store.init_schema()
knowledge_extractor = KnowledgeExtractor()

# 图谱增强检索：注入到 qa_chain
from rag.graph_retriever import GraphRetriever
qa_chain.graph_retriever = GraphRetriever(graph_store)

# 上传文件保存目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploaded_papers")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 上传日志
UPLOAD_LOG = os.path.join(os.path.dirname(__file__), "upload_log.json")


def _log_upload(title: str):
    """记录上传时间"""
    import json
    from datetime import datetime
    try:
        if os.path.exists(UPLOAD_LOG):
            with open(UPLOAD_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append({"title": title, "date": datetime.now().strftime("%Y-%m-%d")})
        with open(UPLOAD_LOG, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False)
    except Exception:
        pass


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: Optional[str] = None
    rewritten_query: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class SearchResult(BaseModel):
    content: str
    title: str
    authors: str
    chunk_index: int


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int


class PaperInfo(BaseModel):
    title: str
    authors: str
    chunks: int
    source: str


class PaperListResponse(BaseModel):
    papers: list[PaperInfo]
    total: int
    total_chunks: int


class SessionInfo(BaseModel):
    id: str
    title: str
    updated_at: str
    created_at: str
    message_count: int


class SessionDetail(BaseModel):
    id: str
    title: str
    summary: str
    created_at: str
    updated_at: str
    messages: list[dict]


# ========== API 端点 ==========

@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "PaperMind API", "version": "2.0.0"}


# ========== 会话管理 ==========

@app.post("/api/sessions", response_model=dict)
async def create_session():
    """创建新会话"""
    session = session_store.create_session()
    return session


@app.get("/api/sessions", response_model=list[SessionInfo])
async def list_sessions():
    """列出所有会话"""
    sessions = session_store.list_sessions()
    return sessions


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    """获取会话详情（含全部消息）"""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = session_store.get_messages(session_id)
    # 解析 sources JSON
    for msg in messages:
        if msg.get("sources"):
            try:
                msg["sources"] = json.loads(msg["sources"])
            except (json.JSONDecodeError, TypeError):
                msg["sources"] = []
        else:
            msg["sources"] = []

    return SessionDetail(
        id=session["id"],
        title=session["title"],
        summary=session["summary"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=messages,
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = session_store.delete_session(session_id)
    if success:
        return {"status": "success", "message": "会话已删除"}
    else:
        raise HTTPException(status_code=404, detail="会话不存在")


# ========== 论文管理 ==========

@app.post("/api/papers/upload", response_model=dict)
async def upload_paper(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    """
    上传 PDF 论文并入库。
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        parser = get_parser("pypdf")
        result = parser.parse(file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF 解析失败: {str(e)}")

    if title and title.strip():
        paper_title = title.strip()
        paper_authors = "unknown"
    else:
        first_page = result.pages[0] if result.pages else result.text[:2000]
        metadata = metadata_extractor.extract(first_page)
        paper_title = metadata["title"] or os.path.splitext(file.filename)[0]
        paper_authors = metadata["authors"] or "unknown"

    if vector_store.has_paper(paper_title):
        return {
            "status": "exists",
            "message": f"论文《{paper_title}》已在知识库中",
            "title": paper_title,
        }

    chunks = split_text(result.text, chunk_size=800, chunk_overlap=100)

    if not chunks:
        raise HTTPException(status_code=422, detail="论文内容为空，无法入库")

    count = vector_store.add_paper(
        chunks=chunks,
        title=paper_title,
        authors=paper_authors,
        source_path=file_path,
    )

    # 同步更新 BM25 索引
    from langchain_core.documents import Document as LCDocument
    bm25_docs = [
        LCDocument(
            page_content=chunk,
            metadata={"title": paper_title, "authors": paper_authors, "chunk_index": i},
        )
        for i, chunk in enumerate(chunks)
    ]
    bm25_store.add_documents(bm25_docs)

    # 知识图谱提取 + 写入 Neo4j
    try:
        graph_data = knowledge_extractor.extract(
            result.text[:3000], title=paper_title, authors=paper_authors
        )
        graph_store.add_paper_graph(graph_data)
    except Exception as e:
        # 图谱提取失败不影响主流程
        print(f"⚠️ 知识图谱提取失败: {e}")

    # 记录上传日志
    _log_upload(paper_title)

    return {
        "status": "success",
        "message": "入库成功",
        "title": paper_title,
        "authors": paper_authors,
        "chunks": count,
        "pages": result.total_pages,
    }


@app.get("/api/papers/upload-history")
async def get_upload_history():
    """获取最近 7 天每天上传论文数量"""
    from datetime import datetime, timedelta
    try:
        if os.path.exists(UPLOAD_LOG):
            with open(UPLOAD_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # 统计最近 7 天
        today = datetime.now().date()
        days = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            count = sum(1 for log in logs if log.get("date") == date_str)
            days.append({"date": date_str, "label": d.strftime("%m/%d"), "count": count})

        return {"days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers", response_model=PaperListResponse)
async def list_papers():
    """列出所有已入库论文"""
    titles = vector_store.list_papers()

    papers = []
    for t in titles:
        paper_chunks = vector_store.get_paper_chunks(t)
        authors = "unknown"
        source = ""
        if paper_chunks:
            meta = paper_chunks[0].metadata
            authors = meta.get("authors", "unknown")
            source = meta.get("source", "")

        papers.append(PaperInfo(
            title=t,
            authors=authors,
            chunks=len(paper_chunks),
            source=source,
        ))

    return PaperListResponse(
        papers=papers,
        total=len(papers),
        total_chunks=vector_store.total_chunks,
    )


@app.delete("/api/papers/{title}")
async def delete_paper(title: str):
    """删除一篇论文"""
    success = vector_store.delete_paper(title)
    if success:
        # 同步更新 BM25 索引
        bm25_store.remove_by_title(title)
        return {"status": "success", "message": f"已删除《{title}》"}
    else:
        raise HTTPException(status_code=404, detail=f"未找到论文《{title}》")


# ========== 问答与检索 ==========

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG 问答。

    - 如果提供 session_id，使用多轮对话模式（带历史、Query 改写）
    - 如果不提供 session_id，使用单次问答模式（向后兼容）
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    question = request.question.strip()

    if request.session_id:
        # 多轮对话模式
        result = qa_chain.ask_with_session(
            question=question,
            session_id=request.session_id,
            k=request.k,
        )
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            session_id=request.session_id,
            rewritten_query=result.get("rewritten_query"),
        )
    else:
        # 单次问答模式（向后兼容）
        result = qa_chain.ask_with_sources(question, k=request.k)
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
        )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式 RAG 问答（SSE）。

    前置步骤（改写、检索、rerank）阻塞执行后，LLM 生成阶段逐 token 返回。

    事件格式：
    data: {"type": "sources", "data": [...]}
    data: {"type": "token", "data": "字"}
    data: {"type": "done", "data": "完整回答"}
    """
    from fastapi.responses import StreamingResponse

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    if not request.session_id:
        raise HTTPException(status_code=400, detail="流式模式需要提供 session_id")

    question = request.question.strip()

    async def event_generator():
        async for event in qa_chain.ask_with_session_stream(
            question=question,
            session_id=request.session_id,
            k=request.k,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """语义检索：在知识库中搜索相关论文片段。"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="搜索内容不能为空")

    docs = vector_store.search(request.query.strip(), k=request.k)

    results = []
    for doc in docs:
        results.append(SearchResult(
            content=doc.page_content,
            title=doc.metadata.get("title", "未知"),
            authors=doc.metadata.get("authors", "unknown"),
            chunk_index=doc.metadata.get("chunk_index", -1),
        ))

    return SearchResponse(results=results, total=len(results))


# ========== 知识图谱 ==========

@app.get("/api/graph")
async def get_graph():
    """获取完整知识图谱（所有节点和边）"""
    try:
        data = graph_store.get_full_graph()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/paper/{title}")
async def get_paper_graph(title: str):
    """获取某篇论文相关的子图"""
    try:
        data = graph_store.get_paper_subgraph(title)
        if not data["nodes"]:
            raise HTTPException(status_code=404, detail=f"未找到论文《{title}》的图谱数据")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/stats")
async def get_graph_stats():
    """获取图谱统计信息"""
    try:
        return graph_store.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"统计查询失败: {str(e)}")


@app.get("/api/graph/keywords")
async def get_keyword_graph():
    """获取关键词关联图（Paper + Concept 二部图）"""
    try:
        data = graph_store.get_keyword_graph()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词图谱查询失败: {str(e)}")


class PapersGraphRequest(BaseModel):
    titles: list[str]


@app.post("/api/graph/papers")
async def get_papers_graph(request: PapersGraphRequest):
    """获取多篇论文的合并子图"""
    if not request.titles:
        raise HTTPException(status_code=400, detail="请提供至少一篇论文标题")
    try:
        data = graph_store.get_papers_subgraph(request.titles)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/concepts")
async def get_concepts():
    """获取所有概念关键词"""
    try:
        concepts = graph_store.get_all_concepts()
        return {"concepts": concepts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/concept-frequency")
async def get_concept_frequency():
    """获取概念被引用频率（按论文数降序）"""
    try:
        data = graph_store.get_concept_frequency()
        return {"concepts": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/method-evolution")
async def get_method_evolution():
    """获取方法改进关系"""
    try:
        data = graph_store.get_method_evolution()
        return {"relations": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/problems-solutions")
async def get_problems_solutions():
    """获取论文解决的问题"""
    try:
        data = graph_store.get_problems_solutions()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/papers-with-concepts")
async def get_papers_with_concepts():
    """获取所有论文及其关键词概念"""
    try:
        data = graph_store.get_papers_with_concepts()
        return {"papers": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== 启动入口 ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
