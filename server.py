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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
from rag.annotation_store import AnnotationStore
from graph.neo4j_store import GraphStore
from graph.extractor import KnowledgeExtractor
from recommend.semantic_scholar import search_papers, get_recommendation_keywords
from recommend.ccf_mapper import CCFMapper
from auth.user_store import UserStore
from auth.jwt_handler import create_access_token, decode_token
from store.upload_log_store import UploadLogStore


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
annotation_store = AnnotationStore()
user_store = UserStore()
upload_log_store = UploadLogStore()

# 认证依赖
_security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_security)) -> str:
    """解码 JWT，返回 user_id；失败自动 401"""
    payload = decode_token(credentials.credentials)
    return payload["sub"]

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
if graph_store.available:
    graph_store.init_schema()
else:
    print("⚠️ Neo4j 不可用，知识图谱功能已降级，其余功能正常运行")
knowledge_extractor = KnowledgeExtractor()

# 图谱增强检索：注入到 qa_chain
from rag.graph_retriever import GraphRetriever
qa_chain.graph_retriever = GraphRetriever(graph_store)

# CCF 映射
ccf_mapper = CCFMapper()

# 上传文件保存目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploaded_papers")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 上传日志（旧版 JSON 路径，仅用于迁移）
UPLOAD_LOG_JSON = os.path.join(os.path.dirname(__file__), "upload_log.json")
# 启动时自动迁移旧版 JSON 数据到 SQLite
upload_log_store.migrate_from_json(UPLOAD_LOG_JSON)


# ========== 工具函数 ==========

def validate_password_strength(password: str) -> str | None:
    """
    校验密码强度：至少 6 位，且包含大写字母、小写字母、数字、特殊字符四种类型中的至少两种。
    返回 None 表示通过，返回字符串为错误提示。
    """
    if len(password) < 6:
        return "密码至少 6 位"
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    types_count = sum([has_upper, has_lower, has_digit, has_special])
    if types_count < 2:
        return "密码需包含大写字母、小写字母、数字、特殊字符中的至少两种"
    return None


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    k: int = 5
    paper_title: Optional[str] = None   # PDF 阅读器：锁定单篇（向后兼容）
    paper_titles: Optional[list[str]] = None  # Chat 页面：多篇论文过滤


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: Optional[str] = None
    rewritten_query: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 5


class PapersGraphRequest(BaseModel):
    titles: list[str]


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
    venue: str = ""


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


# ========== 认证 ==========

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@app.post("/api/auth/register", response_model=AuthResponse)
async def register(data: RegisterRequest):
    """注册新用户"""
    if len(data.username.strip()) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    pwd_error = validate_password_strength(data.password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)
    try:
        user = user_store.create_user(
            username=data.username.strip(),
            password=data.password,
            email=data.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_access_token(user["id"], user["username"])
    return AuthResponse(token=token, user={"id": user["id"], "username": user["username"]})


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """用户登录，返回 JWT token"""
    db_user = user_store.get_user_by_username(data.username)
    if not db_user or not user_store.verify_password(data.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(db_user["id"], db_user["username"])
    return AuthResponse(
        token=token,
        user={"id": db_user["id"], "username": db_user["username"]},
    )


@app.get("/api/auth/me")
async def get_me(user_id: str = Depends(get_current_user)):
    """获取当前用户信息"""
    user = user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


@app.put("/api/auth/password")
async def change_password(data: ChangePasswordRequest, user_id: str = Depends(get_current_user)):
    """修改密码"""
    db_user = user_store.get_user_by_id(user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取完整用户信息（含密码哈希）用于验证旧密码
    full_user = user_store.get_user_by_username(db_user["username"])
    if not full_user or not user_store.verify_password(data.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="当前密码错误")

    pwd_error = validate_password_strength(data.new_password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)

    user_store.update_password(user_id, data.new_password)
    return {"status": "success", "message": "密码修改成功"}


@app.put("/api/auth/profile")
async def update_profile(data: UpdateProfileRequest, user_id: str = Depends(get_current_user)):
    """修改用户名/邮箱，返回新 token"""
    try:
        updated = user_store.update_user_info(user_id, username=data.username, email=data.email)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 用户名可能变了，签发新 token
    token = create_access_token(updated["id"], updated["username"])
    return {
        "token": token,
        "user": {"id": updated["id"], "username": updated["username"], "email": updated.get("email")},
    }


# ========== 会话管理 ==========

@app.post("/api/sessions", response_model=dict)
async def create_session(user_id: str = Depends(get_current_user)):
    """创建新会话"""
    session = session_store.create_session(user_id=user_id)
    return session


@app.get("/api/sessions", response_model=list[SessionInfo])
async def list_sessions(user_id: str = Depends(get_current_user)):
    """列出当前用户的所有会话"""
    sessions = session_store.list_sessions(user_id=user_id)
    return sessions


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, user_id: str = Depends(get_current_user)):
    """获取会话详情（含全部消息）"""
    session = session_store.get_session(session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = session_store.get_messages(session_id)
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
async def delete_session(session_id: str, user_id: str = Depends(get_current_user)):
    """删除会话"""
    success = session_store.delete_session(session_id, user_id=user_id)
    if success:
        return {"status": "success", "message": "会话已删除"}
    else:
        raise HTTPException(status_code=404, detail="会话不存在")


# ========== 论文管理 ==========

@app.post("/api/papers/upload", response_model=dict)
async def upload_paper(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user),
):
    """上传 PDF 论文并入库"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 按用户分目录存储
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, file.filename)

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
        paper_venue = ""
    else:
        first_page = result.pages[0] if result.pages else result.text[:2000]
        metadata = metadata_extractor.extract(first_page)
        paper_title = metadata["title"] or os.path.splitext(file.filename)[0]
        paper_authors = metadata["authors"] or "unknown"
        paper_venue = metadata.get("venue") or ""

    if vector_store.has_paper(paper_title, user_id=user_id):
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
        user_id=user_id,
        venue=paper_venue,
    )

    # 同步更新 BM25 索引
    from langchain_core.documents import Document as LCDocument
    bm25_docs = [
        LCDocument(
            page_content=chunk,
            metadata={"title": paper_title, "authors": paper_authors,
                      "chunk_index": i, "user_id": user_id},
        )
        for i, chunk in enumerate(chunks)
    ]
    bm25_store.add_documents(bm25_docs)

    # 知识图谱提取
    try:
        graph_data = knowledge_extractor.extract(
            result.text[:3000], title=paper_title, authors=paper_authors
        )
        graph_store.add_paper_graph(graph_data, user_id=user_id)
    except Exception as e:
        print(f"⚠️ 知识图谱提取失败: {e}")

    upload_log_store.log(paper_title, user_id=user_id)

    return {
        "status": "success",
        "message": "入库成功",
        "title": paper_title,
        "authors": paper_authors,
        "chunks": count,
        "pages": result.total_pages,
    }


@app.get("/api/papers/upload-history")
async def get_upload_history(user_id: str = Depends(get_current_user)):
    """获取当前用户最近 7 天每天上传论文数量"""
    days = upload_log_store.get_recent_7days(user_id)
    return {"days": days}


@app.get("/api/papers", response_model=PaperListResponse)
async def list_papers(user_id: str = Depends(get_current_user)):
    """列出当前用户已入库论文"""
    titles = vector_store.list_papers(user_id=user_id)

    papers = []
    for t in titles:
        paper_chunks = vector_store.get_paper_chunks(t, user_id=user_id)
        authors = "unknown"
        source = ""
        venue = ""
        if paper_chunks:
            meta = paper_chunks[0].metadata
            authors = meta.get("authors", "unknown")
            source = meta.get("source", "")
            venue = meta.get("venue", "")

        papers.append(PaperInfo(title=t, authors=authors, chunks=len(paper_chunks), source=source, venue=venue))

    return PaperListResponse(papers=papers, total=len(papers), total_chunks=vector_store.total_chunks)


@app.get("/api/papers/{title}/pdf")
async def get_paper_pdf(title: str, token: Optional[str] = None,
                         user_id: Optional[str] = None):
    """根据论文标题获取 PDF 文件（支持 header Bearer 或 ?token= query param）"""
    # 优先从 Authorization header 拿，其次从 query param
    if user_id is None:
        if token:
            try:
                from auth.jwt_handler import decode_token as _decode
                payload = _decode(token)
                user_id = payload["sub"]
            except Exception:
                raise HTTPException(status_code=401, detail="token 无效")
        else:
            raise HTTPException(status_code=401, detail="需要认证")

    paper_chunks = vector_store.get_paper_chunks(title, user_id=user_id)
    if not paper_chunks:
        raise HTTPException(status_code=404, detail=f"未找到论文《{title}》")

    source = paper_chunks[0].metadata.get("source", "")
    if not source or not os.path.isfile(source):
        raise HTTPException(status_code=404, detail="PDF 文件不存在或已被删除")

    real_source = os.path.realpath(source)
    real_user_dir = os.path.realpath(os.path.join(UPLOAD_DIR, user_id))
    if not real_source.startswith(real_user_dir):
        raise HTTPException(status_code=403, detail="访问被拒绝")

    return FileResponse(real_source, media_type="application/pdf",
                        filename=os.path.basename(real_source))


@app.delete("/api/papers/{title}")
async def delete_paper(title: str, user_id: str = Depends(get_current_user)):
    """删除一篇论文（全链路清理：向量库 + BM25 + 知识图谱 + 标注 + PDF文件）"""
    # 1. 删除前先获取论文元数据（source 路径），删除后无法再查
    paper_chunks = vector_store.get_paper_chunks(title, user_id=user_id)
    if not paper_chunks:
        raise HTTPException(status_code=404, detail=f"未找到论文《{title}》")
    source_path = paper_chunks[0].metadata.get("source", "")

    # 2. 从向量库删除
    success = vector_store.delete_paper(title, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到论文《{title}》")

    # 3. 从 BM25 索引删除
    bm25_store.remove_by_title(title)

    # 4. 从知识图谱删除（Paper 节点 + 关系 + 孤立子节点）
    try:
        graph_store.delete_paper_graph(title, user_id=user_id)
    except Exception as e:
        print(f"⚠️ 图谱清理失败: {e}")

    # 5. 删除标注
    try:
        annotation_store.delete_by_paper(title, user_id=user_id)
    except Exception as e:
        print(f"⚠️ 标注清理失败: {e}")

    # 6. 删除 PDF 物理文件
    if source_path and os.path.isfile(source_path):
        try:
            real_source = os.path.realpath(source_path)
            real_user_dir = os.path.realpath(os.path.join(UPLOAD_DIR, user_id))
            if real_source.startswith(real_user_dir):
                os.remove(real_source)
        except Exception as e:
            print(f"⚠️ PDF 文件删除失败: {e}")

    return {"status": "success", "message": f"已删除《{title}》"}


# ========== 标注管理 ==========

class AnnotationCreate(BaseModel):
    paper_title: str
    page: int
    text: str
    note: str = ""
    color: str = "yellow"
    type: str = "highlight"
    rects: list[dict]


class AnnotationUpdate(BaseModel):
    note: Optional[str] = None
    color: Optional[str] = None


@app.get("/api/annotations/{paper_title}")
async def get_annotations(paper_title: str, user_id: str = Depends(get_current_user)):
    """获取某篇论文当前用户的所有标注"""
    annotations = annotation_store.list_by_paper(paper_title, user_id=user_id)
    return {"annotations": annotations}


@app.post("/api/annotations")
async def create_annotation(data: AnnotationCreate, user_id: str = Depends(get_current_user)):
    """创建标注"""
    annotation = annotation_store.create(
        paper_title=data.paper_title,
        page=data.page,
        text=data.text,
        note=data.note,
        color=data.color,
        type=data.type,
        rects=data.rects,
        user_id=user_id,
    )
    return annotation


@app.put("/api/annotations/{annotation_id}")
async def update_annotation(annotation_id: str, data: AnnotationUpdate,
                             user_id: str = Depends(get_current_user)):
    """更新标注"""
    success = annotation_store.update(annotation_id, note=data.note, color=data.color,
                                       user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="标注不存在")
    return {"status": "success"}


@app.delete("/api/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str, user_id: str = Depends(get_current_user)):
    """删除标注"""
    success = annotation_store.delete(annotation_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="标注不存在")
    return {"status": "success"}


# ========== 问答与检索 ==========

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """RAG 问答"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    question = request.question.strip()

    if request.session_id:
        result = qa_chain.ask_with_session(
            question=question,
            session_id=request.session_id,
            k=request.k,
            user_id=user_id,
        )
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            session_id=request.session_id,
            rewritten_query=result.get("rewritten_query"),
        )
    else:
        result = qa_chain.ask_with_sources(question, k=request.k)
        return ChatResponse(answer=result["answer"], sources=result["sources"])


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """流式 RAG 问答（SSE）"""
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
            paper_title=request.paper_title,
            paper_titles=request.paper_titles,
            user_id=user_id,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest, user_id: str = Depends(get_current_user)):
    """语义检索"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="搜索内容不能为空")

    docs = hybrid_retriever.search(request.query.strip(), k=request.k, user_id=user_id)

    results = [
        SearchResult(
            content=doc.page_content,
            title=doc.metadata.get("title", "未知"),
            authors=doc.metadata.get("authors", "unknown"),
            chunk_index=doc.metadata.get("chunk_index", -1),
        )
        for doc in docs
    ]
    return SearchResponse(results=results, total=len(results))


# ========== 知识图谱 ==========

@app.get("/api/graph")
async def get_graph(user_id: str = Depends(get_current_user)):
    try:
        return graph_store.get_full_graph(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/paper/{title}")
async def get_paper_graph(title: str, user_id: str = Depends(get_current_user)):
    try:
        data = graph_store.get_paper_subgraph(title, user_id=user_id)
        if not data["nodes"]:
            raise HTTPException(status_code=404, detail=f"未找到论文《{title}》的图谱数据")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/stats")
async def get_graph_stats(user_id: str = Depends(get_current_user)):
    try:
        return graph_store.get_stats(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"统计查询失败: {str(e)}")


@app.get("/api/graph/keywords")
async def get_keyword_graph(user_id: str = Depends(get_current_user)):
    try:
        return graph_store.get_keyword_graph(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词图谱查询失败: {str(e)}")


@app.post("/api/graph/papers")
async def get_papers_graph(request: PapersGraphRequest, user_id: str = Depends(get_current_user)):
    if not request.titles:
        raise HTTPException(status_code=400, detail="请提供至少一篇论文标题")
    try:
        return graph_store.get_papers_subgraph(request.titles, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱查询失败: {str(e)}")


@app.get("/api/graph/concepts")
async def get_concepts(user_id: str = Depends(get_current_user)):
    try:
        return {"concepts": graph_store.get_all_concepts(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/concept-frequency")
async def get_concept_frequency(user_id: str = Depends(get_current_user)):
    try:
        return {"concepts": graph_store.get_concept_frequency(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/method-evolution")
async def get_method_evolution(user_id: str = Depends(get_current_user)):
    try:
        return {"relations": graph_store.get_method_evolution(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/problems-solutions")
async def get_problems_solutions(user_id: str = Depends(get_current_user)):
    try:
        return {"data": graph_store.get_problems_solutions(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/graph/papers-with-concepts")
async def get_papers_with_concepts(user_id: str = Depends(get_current_user)):
    try:
        return {"papers": graph_store.get_papers_with_concepts(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.post("/api/graph/extract/{title}")
async def reextract_graph(title: str, user_id: str = Depends(get_current_user)):
    """对某篇已入库论文重新运行知识图谱提取"""
    if not graph_store.available:
        raise HTTPException(status_code=503, detail="Neo4j 服务不可用")

    paper_chunks = vector_store.get_paper_chunks(title, user_id=user_id)
    if not paper_chunks:
        raise HTTPException(status_code=404, detail=f"未找到论文《{title}》，请先上传")

    combined_text = "\n\n".join(chunk.page_content for chunk in paper_chunks[:5])[:3000]
    authors = paper_chunks[0].metadata.get("authors", "unknown")

    try:
        graph_data = knowledge_extractor.extract(combined_text, title=title, authors=authors)
        graph_store.add_paper_graph(graph_data, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识图谱提取失败: {str(e)}")

    return {
        "status": "success",
        "message": f"《{title}》知识图谱已重新提取",
        "methods": len(graph_data.get("methods", [])),
        "concepts": len(graph_data.get("concepts", [])),
        "relations": len(graph_data.get("relations", [])),
    }


# ========== 论文推荐 ==========

@app.get("/api/recommend")
async def recommend_papers(range: str = "1year", level: str = "all",
                            user_id: str = Depends(get_current_user)):
    """基于用户研究方向推荐最新论文"""
    from datetime import datetime

    keywords = get_recommendation_keywords(graph_store, user_id=user_id)
    if not keywords:
        return {"papers": [], "keywords": [], "message": "请先上传论文以生成研究画像"}

    current_year = datetime.now().year
    range_map = {"1year": current_year - 1, "6months": current_year, "3months": current_year}
    year_from = range_map.get(range, current_year - 1)

    results = search_papers(keywords, year_from=year_from, limit=20)

    for paper in results:
        paper["ccf_level"] = ccf_mapper.get_level(paper.get("venue", ""))

    if level != "all":
        results = [p for p in results if p.get("ccf_level") == level.upper()]

    return {"papers": results[:10], "keywords": keywords}


# ========== 启动入口 ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
