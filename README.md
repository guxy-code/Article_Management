# PaperMind — 智能学术论文研究平台

> 将 PDF 论文转化为可检索、可对话、可可视化的知识库，帮助研究生和科研人员高效阅读、理解和发现学术文献。

PaperMind 是一个面向研究生和科研人员的 AI 论文管理与分析系统。它以 **LangChain + LangGraph** 为编排核心，融合 **向量数据库（ChromaDB）** 与 **图数据库（Neo4j）** 的双数据库架构，提供从 PDF 上传、智能解析、混合检索问答、知识图谱构建到论文推荐的端到端研究工作流。

---

## 核心亮点

- **双数据库 RAG 架构** — 向量语义检索（ChromaDB）+ 知识图谱结构化关系（Neo4j），回答内容性问题与关系性问题皆可
- **混合检索引擎** — 向量检索 + BM25 关键词检索 + RRF 融合 + LLM 重排序，四阶流水线精准定位论文片段
- **多轮对话记忆系统** — Query 改写（代词消解）+ Token Budget 动态分配 + 自动摘要，长对话不失上下文
- **流式 SSE 输出** — 逐 Token 流式回答，实时反馈检索来源
- **LLM 知识图谱提取** — 自动抽取论文中的方法、问题、概念、数据集及其语义关系，构建可交互的知识网络
- **多用户数据隔离** — 向量库、图数据库、会话、标注全链路 user_id 隔离，JWT 认证保护
- **论文推荐引擎** — 基于知识图谱研究画像，从 Semantic Scholar 检索最新文献，CCF 等级标注与过滤
- **PDF 在线阅读与标注** — 高亮、下划线、删除线、笔记，标注持久化存储，阅读时可直接针对当前论文提问

---

## 技术架构

| 层级 | 技术选型 |
|------|----------|
| **前端** | Next.js 16 · React 19 · TailwindCSS 4 · Framer Motion · React Flow + D3 Force · react-pdf · react-markdown + KaTeX |
| **后端 API** | FastAPI · Uvicorn · Pydantic |
| **AI 编排** | LangChain · LangGraph (ReAct Agent) |
| **向量数据库** | ChromaDB (text-embedding-3-large) |
| **图数据库** | Neo4j (Cypher) |
| **关系数据库** | SQLite (用户 / 会话 / 标注) |
| **大语言模型** | OpenAI 兼容接口（DeepSeek / GPT-4o / 通义千问 / Ollama） |
| **认证** | JWT (python-jose) · bcrypt (SHA-256 预哈希) |
| **外部 API** | Semantic Scholar Graph API |

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                     │
│  Library · AI Chat · Knowledge Graph · Discover · Stats     │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API + SSE (JWT Auth)
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                          │
│  Auth · Sessions · Papers · Annotations · Chat · Recommend  │
├────────────────────────────────────────────────────────────-┤
│                     AI Layer                                │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ RAG Chain │  │ Graph Agent  │  │ Knowledge Extractor  │ │
│  └────┬─────┘  └──────┬───────┘  └──────────┬───────────┘ │
│       │               │                     │              │
│  ┌────▼───────────────▼─────────────────────▼───────────┐  │
│  │         Hybrid Retriever (Vector + BM25 + RRF)        │  │
│  └────┬───────────────────────────────────────────┬──────┘  │
│       │                                           │          │
│  ┌────▼──────┐                              ┌─────▼──────┐   │
│  │ ChromaDB  │                              │   Neo4j    │   │
│  │ (向量检索)  │                              │ (知识图谱)  │   │
│  └───────────┘                              └────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 功能模块详解

### 1. PDF 解析引擎 (`parsers/`)

采用**工厂模式 + 策略模式**，支持两种解析后端，通过 `get_parser(backend)` 切换：

| 解析器 | 特点 | 适用场景 |
|--------|------|----------|
| **PyPDFParser** | 零依赖、速度快、纯 Python | 快速入库、单栏论文 |
| **MinerUParser** | 双栏识别、公式转 LaTeX、表格结构化、输出 Markdown | 高精度解析、复杂排版论文 |

- **MetadataExtractor**：使用 LLM 从论文首页提取标题、作者、摘要、发表场所（venue），远比正则启发式准确
- **ParseResult**：统一数据结构，包含全文文本、元数据、按页拆分文本、解析器标记

### 2. 向量存储 (`store/vector_store.py`)

基于 **ChromaDB** 持久化存储，使用 `text-embedding-3-large` 嵌入模型：

- 论文文本按 800 字 / 100 字重叠切分（`RecursiveCharacterTextSplitter`）
- 每个 chunk 携带完整元数据：title、authors、source、chunk_index、user_id、venue
- 支持 metadata 过滤检索（单篇 / 多篇论文 + user_id 组合 `$and` 过滤）
- 全生命周期 CRUD：`add_paper` → `search` → `list_papers` → `delete_paper`

### 3. BM25 关键词索引 (`store/bm25_store.py`)

自研**学术文本分词器** `tokenize_academic()`：

- 英文连续串正则保留整词（`FedAvg`、`Non-IID`、`SCAFFOLD` 不会被拆开）
- 中文部分使用 **jieba** 分词，过滤单字噪声
- 基于 `rank_bm25.BM25Okapi` 的内存索引，支持增量添加与按论文删除

### 4. 混合检索引擎 (`store/hybrid_retriever.py`)

四阶检索流水线：

```
Query → ① 向量检索 (fetch_k = k×4) + BM25 检索 (fetch_k)
      → ② RRF 融合 (Reciprocal Rank Fusion, k=60)
      → ③ LLM Batch 重排序
      → ④ Top-K 返回
```

- **RRF 融合公式**：`score(d) = 1/(60 + rank_vector) + 1/(60 + rank_bm25)`
- 文档唯一标识：`title::chunk_index`，避免重复计分
- Metadata 过滤贯穿向量与 BM25 两路

### 5. LLM 重排序器 (`store/reranker.py`)

- 候选文档截断到 200 字，一次 LLM 调用完成全量排序
- 输出编号序列（如 `3,1,5,2,4`），正则解析 + 去重 + 补位
- 失败自动降级为原始顺序的前 Top-K

### 6. RAG 问答链 (`rag/qa_chain.py`)

支持三种问答模式：

| 方法 | 模式 | 说明 |
|------|------|------|
| `ask_with_sources()` | 单次问答 | 无历史，向量 + 图谱增强 |
| `ask_with_session()` | 多轮对话 | 带 session 历史 + 摘要 + Query 改写 |
| `ask_with_session_stream()` | 流式 SSE | 逐 Token 输出，先推送来源再推送回答 |

- **论文范围锁定**：支持单篇（PDF 阅读器场景）和多篇（Chat 页面选择器）过滤
- **图谱增强**：每次问答自动注入知识图谱结构化关系上下文
- **来源追溯**：每条回答附带来源论文标题 + chunk 编号 + 内容预览

### 7. Query 改写器 (`rag/query_rewriter.py`)

解决多轮对话中的**指代消解**问题：

- 正则检测代词/指代词（`它`、`这个方法`、`该算法`、`this`、`the above` 等）
- 短问题（<15 字）强制改写
- 输出：改写后的独立查询 + 论文标题关键词（用于 metadata 过滤）
- 改写失败自动降级为原始 query

### 8. 对话记忆管理 (`rag/conversation_memory.py`)

- **Token Budget 动态分配**：根据检索 chunks 长度自适应历史预算（2000–4000 字符）
- **自动摘要**：每 6 条消息触发 LLM 生成 3–5 句对话摘要
- **分层截断**：Query 改写用轻量上下文（assistant 截断 150 字），Prompt 用详细上下文（assistant 截断 300 字）
- **从近到远**的消息组装策略，优先保留近期上下文

### 9. 图谱增强检索 (`rag/graph_retriever.py`)

- LLM 从用户问题中提取实体 + 判断问题类型（关系性 vs 内容性）
- 关系性问题：查询两实体间最短路径（≤5 跳）
- 内容性问题：查询实体关联关系（模糊匹配 + 精确匹配）
- 三元组去重 + 格式化为 `主语 --[关系]--> 宾语` 文本

### 10. 知识图谱系统 (`graph/`)

#### 知识提取 (`graph/extractor.py`)

LLM 从论文前 3000 字中提取五类结构化知识：

| 类型 | 说明 |
|------|------|
| **methods** | 论文提出的核心方法/算法 |
| **problems** | 论文要解决的研究问题 |
| **concepts** | 核心技术概念 |
| **datasets** | 实验数据集 |
| **relations** | IMPROVES / SOLVES / USES 语义关系 |

#### Neo4j 存储 (`graph/neo4j_store.py`)

- **节点类型**：Paper、Method、Problem、Dataset、Concept
- **关系类型**：PROPOSES、ADDRESSES、EVALUATES_ON、USES_CONCEPT、IMPROVES、SOLVES、USES
- **多用户隔离**：所有节点携带 `user_id` 属性，复合唯一约束 `(name, user_id)`
- **Schema 自迁移**：自动识别并删除旧版单字段唯一约束，创建新的复合约束
- **丰富查询 API**：

| 查询 | 说明 |
|------|------|
| `get_full_graph()` | 当前用户完整图谱 |
| `get_paper_subgraph()` | 单篇论文 2 跳子图 |
| `get_papers_subgraph()` | 多篇论文合并子图 |
| `get_keyword_graph()` | Paper-Concept 二部图 |
| `get_concept_frequency()` | 概念出现频率（降序） |
| `get_method_evolution()` | 方法改进链 |
| `get_problems_solutions()` | 论文-问题映射 |
| `query_path()` | 两实体间最短路径 |
| `query_related()` | 实体关联关系 |

- **优雅降级**：Neo4j 不可用时自动跳过，其余功能正常运行

### 11. 论文推荐 (`recommend/`)

- **Semantic Scholar API** (`semantic_scholar.py`)：
  - 带内存缓存（1 小时 TTL），避免重复请求
  - 429 限流自动等待 3 秒重试
  - 返回标题、作者、年份、场所、URL、开放获取 PDF 链接
- **CCF 等级映射** (`ccf_mapper.py`)：
  - 从 `ccf_venues.json` 构建缩写 + 全称双向查找表
  - 支持精确匹配与模糊匹配
  - 返回 A / B / C 等级
- **推荐策略**：从知识图谱提取用户 Top-3 高频概念作为研究画像关键词，按时间范围（1 年 / 半年 / 3 个月）和 CCF 等级（A / B / C）筛选

### 12. 用户认证系统 (`auth/`)

- **JWT Token** (`jwt_handler.py`)：HS256 签名，默认 7 天有效期，payload 含 user_id + username
- **用户存储** (`user_store.py`)：
  - SQLite 持久化，bcrypt 哈希密码
  - **SHA-256 预哈希**：将任意长度密码转为固定 64 字节，规避 bcrypt 72 字节限制
  - 密码强度校验：至少 6 位，包含大写字母、小写字母、数字、特殊字符中的至少两种
  - 支持用户名/邮箱修改并签发新 Token
- **FastAPI 集成**：`HTTPBearer` 依赖注入，所有受保护端点自动解码 JWT

### 13. 会话与标注持久化 (`rag/session_store.py`, `rag/annotation_store.py`)

- **会话存储**：SQLite，sessions + messages 两表，外键级联删除，多用户隔离
- **标注存储**：SQLite，支持高亮/下划线/删除线三种类型，存储颜色、笔记、矩形坐标，多用户隔离
- **自动迁移**：已有表自动补充新字段（`user_id`、`type`），向后兼容

### 14. LangGraph ReAct Agent (`main.py` + `tools.py`)

命令行交互模式，基于 `langgraph.prebuilt.create_react_agent`：

| Tool | 功能 |
|------|------|
| `add_paper` | 上传 PDF → 解析 → 切分 → 入库 |
| `ask_paper` | 基于论文内容的 RAG 问答 |
| `search_papers` | 语义检索论文片段（不经 LLM 生成） |
| `list_papers` | 列出知识库论文清单 |
| `delete_paper` | 删除指定论文 |

---

## 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| **Home** | `/` | 工作台首页，上传统计与快捷入口 |
| **Library** | `/library` | 论文库管理，上传/删除/在线 PDF 阅读 + 标注 |
| **AI Chat** | `/chat` | 多轮智能问答，流式输出，论文范围选择，会话历史管理 |
| **Knowledge** | `/knowledge` | 知识图谱交互式可视化（React Flow + D3 力导向布局） |
| **Discover** | `/discover` | AI 论文推荐，按时间范围和 CCF 等级筛选 |
| **Stats** | `/stats` | 研究数据统计面板，概念频率/方法演进/问题映射 |
| **Settings** | `/settings` | 个人信息与密码管理 |
| **Login** | `/login` | 登录 / 注册 |

### 前端技术细节

- **PDF 阅读器**：基于 `react-pdf`，支持高亮标注层（`annotation-layer`）、标注面板、标注气泡、高亮工具栏
- **图谱可视化**：`@xyflow/react` (React Flow) + `d3-force` 力导向布局，支持单篇子图 / 多篇对比 / 关键词共现网络
- **Markdown 渲染**：`react-markdown` + `remark-gfm` + `remark-math` + `rehype-katex`，支持 LaTeX 公式
- **流式 Chat**：SSE 解析，先接收来源再逐 Token 渲染回答
- **认证**：JWT 存 localStorage，前端解析 `exp` 检测过期，`authFetch` 自动携带 Authorization header

---

## 数据流

```
PDF 上传
  │
  ├─→ PyPDF/MinerU 解析 → 全文 + 元数据
  │     │
  │     ├─→ 文本切分 (800字/100重叠) → ChromaDB 向量入库 + BM25 索引
  │     │
  │     └─→ LLM 知识提取 → Neo4j 图谱写入 (Method/Problem/Concept/Dataset)
  │
  └─→ PDF 文件按用户分目录存储

用户提问
  │
  ├─→ Query 改写 (代词消解 + 论文过滤)
  │
  ├─→ 混合检索: 向量 + BM25 → RRF 融合 → LLM 重排序
  │
  ├─→ 图谱增强: 实体提取 → Neo4j 关系查询
  │
  ├─→ 对话记忆: 历史组装 (Token Budget) + 摘要注入
  │
  └─→ LLM 生成 → 流式 SSE 输出 + 来源追溯 → 会话持久化
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Neo4j 5.x（可选，不装则知识图谱功能自动降级）

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# LLM 配置（OpenAI 兼容接口，支持 DeepSeek / GPT-4o / 通义千问 / Ollama）
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-your-key-here
MODEL_NAME=deepseek-v4-flash

# Embedding 配置（可与 LLM 使用不同 provider）
# EMBEDDING_API_KEY=sk-your-embedding-key
# EMBEDDING_BASE_URL=https://api.openai.com/v1
# EMBEDDING_MODEL=text-embedding-3-large

# JWT 认证
JWT_SECRET_KEY=your-random-secret-at-least-32-chars
JWT_EXPIRE_HOURS=168

# Neo4j（可选，不配置则知识图谱功能自动降级）
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your-password
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 启动后端

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

API 文档自动生成：http://localhost:8000/docs

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端访问：http://localhost:3000

### 5. （可选）命令行 Agent 模式

```bash
python main.py
```

### 6. （可选）测试连通性

```bash
python test_connection.py
```

---

## 支持的 LLM

本项目使用 OpenAI 兼容接口，只需修改 `.env` 中的 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY` 即可切换：

| 模型 | BASE_URL | 说明 |
|------|----------|------|
| DeepSeek | `https://api.deepseek.com/v1` | 国内直连，性价比高 |
| OpenAI GPT-4o | `https://api.openai.com/v1` | 默认 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云 |
| 本地 Ollama | `http://localhost:11434/v1` | 免费本地部署 |

---

## 项目结构

```
Article_Management/
├── server.py                  # FastAPI 后端入口 (API 路由 + 业务逻辑)
├── main.py                     # LangGraph ReAct Agent 命令行入口
├── tools.py                    # Agent 工具封装 (add/ask/search/list/delete)
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── ccf_venues.json             # CCF 会议/期刊等级数据
│
├── parsers/                    # PDF 解析引擎
│   ├── base.py                 #   抽象基类 PaperParser + ParseResult
│   ├── pypdf_parser.py         #   PyPDF 轻量解析器
│   ├── mineru_parser.py        #   MinerU 高精度解析器 (可选)
│   └── metadata_extractor.py   #   LLM 元数据提取
│
├── store/                      # 存储与检索层
│   ├── vector_store.py         #   ChromaDB 向量存储
│   ├── bm25_store.py           #   BM25 关键词索引 (学术分词)
│   ├── hybrid_retriever.py     #   混合检索 (Vector + BM25 + RRF + Rerank)
│   ├── reranker.py             #   LLM Batch 重排序
│   └── text_splitter.py        #   文本切分
│
├── rag/                        # RAG 问答层
│   ├── qa_chain.py             #   问答链 (单次/多轮/流式)
│   ├── query_rewriter.py       #   Query 改写 (代词消解)
│   ├── conversation_memory.py  #   对话记忆 (Token Budget + 摘要)
│   ├── graph_retriever.py      #   图谱增强检索
│   ├── session_store.py        #   会话持久化 (SQLite)
│   └── annotation_store.py     #   PDF 标注持久化 (SQLite)
│
├── graph/                      # 知识图谱层
│   ├── extractor.py            #   LLM 三元组提取
│   └── neo4j_store.py          #   Neo4j 图数据库操作
│
├── recommend/                   # 论文推荐层
│   ├── semantic_scholar.py     #   Semantic Scholar API + 缓存
│   └── ccf_mapper.py           #   CCF 等级映射
│
├── auth/                       # 认证层
│   ├── jwt_handler.py          #   JWT 生成与验证
│   └── user_store.py           #   用户存储 (SQLite + bcrypt)
│
├── frontend/                   # Next.js 前端
│   ├── src/app/                #   页面路由 (App Router)
│   ├── src/components/          #   组件 (layout/library/ui)
│   └── src/lib/                #   工具库 (api/auth/conversations)
│
├── uploaded_papers/            # 上传 PDF 文件 (按用户分目录)
├── chroma_db/                  # ChromaDB 持久化数据
└── sessions.db                 # SQLite 数据库 (用户/会话/标注)
```

---

## API 接口概览

| 分类 | 端点 | 方法 | 说明 |
|------|------|------|------|
| **认证** | `/api/auth/register` | POST | 注册 |
| | `/api/auth/login` | POST | 登录 |
| | `/api/auth/me` | GET | 获取当前用户 |
| | `/api/auth/password` | PUT | 修改密码 |
| | `/api/auth/profile` | PUT | 修改用户名/邮箱 |
| **会话** | `/api/sessions` | POST | 创建会话 |
| | `/api/sessions` | GET | 会话列表 |
| | `/api/sessions/{id}` | GET | 会话详情 |
| | `/api/sessions/{id}` | DELETE | 删除会话 |
| **论文** | `/api/papers/upload` | POST | 上传 PDF |
| | `/api/papers` | GET | 论文列表 |
| | `/api/papers/{title}/pdf` | GET | 获取 PDF 文件 |
| | `/api/papers/{title}` | DELETE | 删除论文 |
| | `/api/papers/upload-history` | GET | 上传统计 |
| **标注** | `/api/annotations/{paper}` | GET | 获取标注 |
| | `/api/annotations` | POST | 创建标注 |
| | `/api/annotations/{id}` | PUT | 更新标注 |
| | `/api/annotations/{id}` | DELETE | 删除标注 |
| **问答** | `/api/chat` | POST | RAG 问答 |
| | `/api/chat/stream` | POST | 流式 SSE 问答 |
| | `/api/search` | POST | 语义检索 |
| **图谱** | `/api/graph` | GET | 完整图谱 |
| | `/api/graph/paper/{title}` | GET | 论文子图 |
| | `/api/graph/papers` | POST | 多论文子图 |
| | `/api/graph/keywords` | GET | 关键词图谱 |
| | `/api/graph/stats` | GET | 图谱统计 |
| | `/api/graph/concepts` | GET | 概念列表 |
| | `/api/graph/concept-frequency` | GET | 概念频率 |
| | `/api/graph/method-evolution` | GET | 方法演进 |
| | `/api/graph/problems-solutions` | GET | 问题-方案 |
| | `/api/graph/papers-with-concepts` | GET | 论文-概念 |
| | `/api/graph/extract/{title}` | POST | 重新提取图谱 |
| **推荐** | `/api/recommend` | GET | 论文推荐 |

---

## 功能演进路线

- **第一期** — PDF 上传 → 向量存储 → 语义检索问答
- **第二期** — Neo4j 知识图谱集成 → 图谱增强检索 → 可视化
- **第三期** — 对话记忆机制 → 论文推荐引擎 → 多用户认证

---

## 开发者

**gxy**
