<p align="center">
  <img src="https://img.shields.io/badge/PaperMind-AI%20Research%20Workspace-blue?style=for-the-badge&logo=bookstack&logoColor=white" alt="PaperMind" />
</p>

<h1 align="center">🧠 PaperMind</h1>

<p align="center">
  <strong>一个会"生长"的 AI 学术研究工作台</strong><br/>
  <em>将 PDF 论文转化为可检索、可对话、可可视化、可生长的知识库</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=next.js" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangChain-0.2+-green?logo=chainlink" alt="LangChain" />
  <img src="https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j" alt="Neo4j" />
  <img src="https://img.shields.io/badge/ChromaDB-0.5+-orange" alt="ChromaDB" />
  <img src="https://img.shields.io/badge/DeepSeek%20%7C%20GPT--4o-LLM-purple" alt="LLM" />
</p>

---

## 💡 PaperMind 是什么

PaperMind 不是又一个论文管理工具。它是一个**有记忆、能生长、懂你研究方向**的 AI 研究伙伴。

传统的论文工具止步于"存储 + 检索"。PaperMind 在此基础上构建了三层递进的智能：

| 层级 | 能力 | 传统工具 | PaperMind |
|:---:|------|:---:|:---:|
| L1 | 论文解析 & 检索 | ✅ | ✅ 混合检索 + LLM 重排序 |
| L2 | 知识图谱 & 关系推理 | ❌ | ✅ 自动抽取 + 交互可视化 |
| L3 | 自生长记忆 & 兴趣图谱 | ❌ | ✅ 从交互中学习，越用越懂你 |

> **核心理念**：系统从"被动检索工具"进化为"主动研究伙伴"——它记得你问过什么、关注什么、理解到什么程度，并据此个性化每一次回答和推荐。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js 16 + React 19)                │
│   Library · AI Chat · Knowledge Graph · Memory · Discover · Stats   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST API + SSE Stream (JWT Auth)
┌────────────────────────────────▼────────────────────────────────────┐
│                         FastAPI Backend                              │
│   Auth · Papers · Sessions · Annotations · Chat · Recommend         │
├─────────────────────────────────────────────────────────────────────┤
│                          AI Layer                                    │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │  RAG Chain   │  │ Memory Distiller │  │ Knowledge Extractor   │  │
│  │  + Rewriter  │  │ + Interest Graph │  │ + Structure Reviewer  │  │
│  └──────┬───────┘  └────────┬─────────┘  └───────────┬───────────┘  │
│         │                   │                         │              │
│  ┌──────▼───────────────────▼─────────────────────────▼───────────┐  │
│  │          Hybrid Retriever (Vector + BM25 + RRF + Rerank)        │  │
│  └──────┬──────────────────────────────────────────────┬───────────┘  │
│         │                                              │              │
│  ┌──────▼──────┐  ┌────────────┐  ┌───────────────────▼───────────┐  │
│  │  ChromaDB   │  │   SQLite   │  │         Neo4j              │  │
│  │  向量检索    │  │ 会话/标注   │  │  论文图谱 + 用户兴趣图谱    │  │
│  └─────────────┘  └────────────┘  └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```


### 技术栈一览

| 层级 | 选型 |
|------|------|
| **前端框架** | Next.js 16 · React 19 · TailwindCSS 4 · Framer Motion |
| **图谱可视化** | Cytoscape.js · D3-Force · React Flow |
| **PDF 阅读** | react-pdf · 自研标注层（高亮/下划线/笔记） |
| **数学渲染** | react-markdown + remark-math + rehype-katex |
| **后端 API** | FastAPI · Uvicorn · Pydantic |
| **AI 编排** | LangChain 0.2 · LangGraph (ReAct Agent) |
| **向量数据库** | ChromaDB（text-embedding-3-large，cosine） |
| **图数据库** | Neo4j 5（Cypher，双图谱：论文 + 用户兴趣） |
| **关系数据库** | SQLite（用户/会话/标注/记忆元数据） |
| **大语言模型** | OpenAI 兼容接口 — DeepSeek / GPT-4o / 通义千问 / Ollama |
| **认证** | JWT (python-jose) · bcrypt (SHA-256 预哈希) |
| **外部 API** | Semantic Scholar Graph API · CCF 等级映射 |
| **部署** | Docker Compose（三容器：前端 + 后端 + Neo4j） |

---

## 🚀 核心功能

### 1. 智能论文管理 (`Library`)

- **一键上传 PDF**，自动解析全文并通过 LLM 提取元数据（标题、作者、摘要、发表场所）
- **双解析引擎**：PyPDF（快速）/ MinerU（高精度，支持双栏、公式转 LaTeX、表格结构化）
- **在线 PDF 阅读器** + 持久化标注系统（高亮、下划线、删除线、笔记，按用户隔离）
- 论文阅读状态追踪（未读 / 在读 / 已读）
- 支持按论文标题筛选检索范围

### 2. 多轮智能问答 (`Chat`)

基于论文内容的深度对话，不是简单的"找片段贴回来"：

```
用户提问 → Query 改写（代词消解）→ 混合检索 → RRF 融合 → LLM 重排序
    → 图谱关系补充 → 记忆注入 → 画像注入 → 流式生成回答
    → 异步蒸馏记忆 → 异步更新兴趣图谱
```

**检索管线详解**：

| 阶段 | 技术 | 作用 |
|------|------|------|
| Stage 1 | 向量检索 (ChromaDB, fetch_k=4×k) | 语义相似度召回 |
| Stage 2 | BM25 关键词检索 (jieba + 学术分词) | 专业术语精确匹配 |
| Stage 3 | RRF 融合 (k=60) | 双路结果去重 + 排序融合 |
| Stage 4 | LLM 重排序 | 按与问题的相关性精排 Top-K |

**对话记忆管理**：
- Token Budget 动态分配：摘要占 40%，近轮对话按预算逐条填入
- 自动摘要生成：对话过长时 LLM 压缩前文为 3-5 句摘要
- 会话持久化：所有对话历史存储在 SQLite，支持历史回顾与续聊

### 3. 知识图谱 (`Knowledge`)

**LLM 自动抽取**论文中的实体与关系：

- 实体类型：`Method` · `Problem` · `Concept` · `Dataset`
- 关系类型：`PROPOSES` · `SOLVES` · `USES` · `EVALUATES_ON` · `EXTENDS`
- 基于论文前 N 字 + 元数据，一次 LLM 调用完成结构化抽取

**交互式可视化**：
- 力导向图布局（D3-Force）
- 支持单篇论文子图 / 全库图谱 / 多篇对比视图
- 节点点击查看详情，边悬浮显示关系描述

### 4. 自生长记忆系统 (`Memory`)

> 这是 PaperMind 区别于所有论文工具的核心创新。

系统从每次问答交互中**异步蒸馏**关键知识点，构建三层记忆架构：

```
┌────────────────────────────────────────────┐
│  画像层 (User Research Profile)              │
│  从知识树+记忆库聚合，LLM 生成自然语言画像    │
├────────────────────────────────────────────┤
│  记忆层 (Core Knowledge Memory)              │
│  问答蒸馏的知识条目，带重要性分数 + 查重合并   │
├────────────────────────────────────────────┤
│  知识树层 (Domain Knowledge Tree)            │
│  Neo4j 节点 mastery/query_count 属性         │
└────────────────────────────────────────────┘
```

**工作原理**：
1. 每次问答后，规则过滤 + LLM 蒸馏提取一条知识点
2. 写入前向量查重：cosine distance < 0.15 则合并到已有记忆（不会无限膨胀）
3. 追问回溯：连续追问同一话题时，前序记忆 importance +0.3
4. 检索时复合排序：`similarity×0.7 + importance×0.2 + access_bonus×0.1`
5. 记忆被引用后 importance 自动强化，不重要的自然沉淀

**对问答的增强**：记忆在每次回答前同步注入 prompt，让 AI 记得"你上周问过 FedAvg 的通信效率，当时的结论是..."


### 5. 用户研究兴趣图谱 (`Memory` 页面)

一张以用户为中心、随交互自动生长的**结构化研究方向地图**：

- **三级层次**：`Field`（大方向）→ `Topic`（子方向）→ `Entity`（具体方法/概念）
- **三种关系**：`CONTAINS`（层级包含）· `RELATES_TO`（语义关联）· `COMPARES_WITH`（对比）
- **自动生长**：每次问答异步提取涉及的概念，MERGE 到图谱中
- **权重衰减**：60 天未触及的 Topic 自动衰减，90 天 + 低权重 → dormant
- **结构审视**：累计 N 次更新后，LLM 审视整体结构，归纳新的 Field 节点、修正层级
- **容量治理**：活跃节点上限 300，超额时最低权重节点转 dormant

**与论文图谱的区别**：
| | 论文图谱 | 兴趣图谱 |
|---|---|---|
| 描述对象 | 论文的客观内容 | 用户的主观关注 |
| 变化频率 | 写入后不变 | 每次交互都可能变化 |
| 有无遗忘 | 无 | 有（分层衰减） |

### 6. 论文推荐引擎 (`Discover`)

- 基于知识图谱 + 兴趣图谱生成**研究画像关键词**
- 从 **Semantic Scholar** 检索最新相关文献
- 支持按时间范围筛选（近 1 年 / 半年 / 3 个月）
- **CCF 等级标注与过滤**（A / B / C 类会议期刊，基于本地 JSON 映射）
- 一键查看论文详情、外链跳转

### 7. 研究统计面板 (`Stats`)

- 论文总数、知识图谱节点数、关系数、方法数
- 研究主题频率分布图
- 论文覆盖度热力图
- 记忆条目数、兴趣图谱节点数、健康度指标

---

## 📐 设计亮点

### 多用户数据隔离

全链路 `user_id` 隔离，每个用户拥有独立的：
- 向量库文档（ChromaDB metadata filter）
- 知识图谱子图（Neo4j 节点属性）
- 兴趣图谱（`UserTopic` 节点 user_id 联合唯一键）
- 会话 / 标注 / 记忆 / 画像

### 优雅降级

所有可选组件不可用时系统自动降级，不影响核心功能：
- Neo4j 不可用 → 知识图谱 & 兴趣图谱功能关闭，论文管理 & 问答正常
- 记忆库初始化失败 → 问答仍可用，只是不注入记忆上下文
- Embedding API 异常 → 错误提示但不崩溃

### 异步不阻塞

所有"生长型"操作（记忆蒸馏、兴趣图谱更新、画像重算）均为 **fire-and-forget 异步**，不增加用户感知延迟。单轮问答的同步 LLM 调用次数不增加。

### 幂等写入

Neo4j 全部使用 `MERGE` 语义，ChromaDB 记忆写入前向量查重，确保重复操作不产生脏数据。

---

## 🛠️ 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-org/papermind.git
cd papermind

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key

# 3. 一键启动
docker compose up -d

# 前端：http://localhost:3000
# 后端 API 文档：http://localhost:8000/docs
# Neo4j Browser：http://localhost:7474（如开放端口）
```

### 方式二：本地开发

```bash
# ===== 后端 =====
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入：
#   OPENAI_API_KEY=sk-xxx
#   OPENAI_BASE_URL=https://api.deepseek.com/v1
#   MODEL_NAME=deepseek-v4-flash
#   EMBEDDING_MODEL=text-embedding-3-large
#   NEO4J_URI=bolt://localhost:7687（可选）

# 启动后端
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# ===== 前端 =====
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

### 环境变量说明

| 变量 | 必填 | 说明 |
|------|:---:|------|
| `OPENAI_API_KEY` | ✅ | LLM API Key（支持 DeepSeek / OpenAI / 通义千问） |
| `OPENAI_BASE_URL` | ✅ | API 端点 URL |
| `MODEL_NAME` | ✅ | 模型名称（如 `deepseek-v4-flash`） |
| `EMBEDDING_MODEL` | ✅ | 嵌入模型（如 `text-embedding-3-large`） |
| `EMBEDDING_API_KEY` | ❌ | 嵌入模型独立 Key（不填则复用 OPENAI_API_KEY） |
| `EMBEDDING_BASE_URL` | ❌ | 嵌入模型独立端点（不填则复用 OPENAI_BASE_URL） |
| `NEO4J_URI` | ❌ | Neo4j 连接地址（不配置则图谱功能自动降级） |
| `NEO4J_USER` | ❌ | Neo4j 用户名（默认 `neo4j`） |
| `NEO4J_PASSWORD` | ❌ | Neo4j 密码 |
| `JWT_SECRET_KEY` | ❌ | JWT 签名密钥（生产环境务必修改） |
| `JWT_EXPIRE_HOURS` | ❌ | Token 过期时间（默认 168 小时） |
| `DB_PATH` | ❌ | SQLite 路径（Docker 部署时自动设置） |


---

## � 技术深度解析

> 以下是一些值得单独说明的工程设计，体现了系统在"可用"之上追求"精细"的思考。

### 兴趣图谱：对齐蒸馏 + 实体标准化

蒸馏 Prompt 中注入当前 **Top-20 活跃节点名**，引导 LLM 复用已有命名而非创造同义新节点。配合 `normalize()` 函数做缩写映射（`FL → Federated Learning`）和去后缀（`SCAFFOLD算法 → SCAFFOLD`），从 Prompt 层 + 代码层双重防止节点碎片化。

### 兴趣图谱：四维 Interest Score

检索注入时不是简单按 weight 排序，而是计算综合兴趣分：

```
Interest Score = Recency×0.3 + Frequency×0.3 + Duration×0.2 + Behavior×0.2
```

- **Recency**：半衰期 30 天的指数衰减（`0.5^(days/30)`）
- **Frequency**：命中次数归一化（`min(hit_count/10, 1.0)`）
- **Duration**：关注持续时间（首次→最近，`min(days/90, 1.0)`）
- **Behavior**：节点权重（累计强化值）

### 兴趣图谱：结构审视器（自动归纳）

每 20 次蒸馏后触发一次 LLM 结构审视，检查图谱完整性并自动执行：
- **同义合并**：识别 `"FedAvg"` 和 `"Federated Averaging"` 是同一概念，关系迁移后合并
- **层级补充**：`SCAFFOLD`、`FedProx` 应归入 `通信效率优化` Topic 下
- **Field 归纳**：3 个以上同方向 Topic/Entity 自动归纳出上层 `Field` 节点
- Token 控制：只传 weight > 0.2 的前 80 个节点，不传完整 description

### 兴趣图谱：生命周期管理

- **衰减**：Topic 超 60 天未触及 → weight × 0.9
- **休眠**：Entity 超 90 天 + weight < 0.1 → status="dormant"（不删除，只是不再注入）
- **唤醒**：dormant 节点被再次问及 → status="active"，weight 重置 0.3
- **容量治理**：活跃节点上限 300，超额时最低 weight 批量转 dormant
- **软删除**：用户手动删除的节点 30 天内可恢复

### 记忆蒸馏：效果追踪闭环

蒸馏不只是"写入然后忘记"，而是有完整的效果验证：
1. 记忆被注入 prompt 后，AI 生成回答
2. 下一轮蒸馏时，用记忆前 20 字作为**指纹**扫描回答文本
3. 如果匹配 → `times_used +1`，证明这条记忆确实对回答有帮助
4. 高 `times_used` 的记忆在后续排序中获得更高优先级

### 记忆蒸馏：认知轨迹链

通过 `prev_memory_id` 字段将同一会话中连续蒸馏的记忆串成链：
- 追问同一话题时，前序记忆被追问 → `importance +0.3`（说明用户在深入）
- 链的长度本身就反映了用户对某话题的探索深度
- 未来可据此生成"用户是如何从 A 概念一步步深入到 B 概念的"认知路径

### 用户画像：多信号聚合 + 认知阶段判定

画像不是简单的"你研究 X 方向"，而是从 5 个信号源聚合：
1. 记忆库 Top-10（knowledge + importance）
2. 高频主题 Top-10（跨记忆的 topics 频率统计）
3. 最近 30 条提问历史
4. 论文知识图谱概念频率
5. 已上传论文标题列表

LLM 据此判定用户所处**认知阶段**：
- 基础理解（"什么是 X"）→ 方案对比（"A 和 B 的区别"）→ 实验验证（"效果如何"）

### 用户画像：惰性刷新策略

画像生成是高成本操作（一次 LLM 调用），采用"本次用旧、后台重算"的策略：
- 问答时同步读 SQLite 缓存（0ms）
- 判断是否需要刷新（新增 ≥10 轮问答 或 距上次 >7 天）
- 如需刷新 → `asyncio.create_task` fire-and-forget，本次问答不等待
- 下次问答自然使用新画像

### 知识树：阈值门控 + 状态机

防止功能过早暴露给新用户（数据不足时可视化无意义）：
- **解锁条件**：论文 ≥ 3 篇 且 记忆 ≥ 10 条
- **mastery 状态机**：`unexplored → learning（首次被问）→ mastered（被问 ≥3 次）`
- 每次蒸馏提取的 topics 自动映射到 Neo4j 节点，更新 `query_count` 驱动状态迁移

### 图谱增强检索：问题类型识别

不是所有问题都需要知识图谱。系统通过 LLM 判断 `is_relational`：
- **关系性问题**（"A 和 B 有什么关系"）→ 先走 `query_path` 找两实体间路径，再补充邻居关系
- **内容性问题**（"解释一下 X"）→ 只查实体邻居关系作为补充
- Neo4j 不可用时自动跳过，不浪费 LLM 调用（先检查 `available` 再决定是否提取实体）

### LLM Batch 重排序

不是对每个候选单独打分（N 次 LLM 调用），而是一次性将所有候选（每个截断 200 字）送入 LLM 做排序：
- 输出格式：`3,1,5,2,4`（编号序列）
- 解析容错：正则提取数字 + 去重 + 边界检查
- 候选 ≤ top_k 时直接跳过（避免浪费）
- 失败降级：返回原序前 K 个

### 论文上传时的兴趣种子

论文上传不仅建立知识图谱，还会以**低权重种子**方式将关键概念注入用户兴趣图谱：
- 抽取的 `methods` / `concepts` 以 `weight = 0.1`（SEED_WEIGHT）加入
- 后续用户在问答中提及这些概念时，自然被强化到正常权重
- 未被问及的概念随时间衰减→休眠，不会污染图谱

### SSE 流式问答 + 异步后处理

流式回答与记忆蒸馏完全解耦：
1. 检索阶段先 yield `sources`（前端立即显示来源卡片）
2. LLM 生成阶段逐 token yield（前端实时渲染 Markdown）
3. 全部生成完毕 yield `done`
4. SSE 连接关闭**之后**，fire-and-forget 执行记忆蒸馏 + 兴趣蒸馏 + 画像检查
5. 用户感知延迟 = 纯 LLM 生成时间，后处理对用户完全透明

---

## �📁 项目结构

```
papermind/
├── server.py                  # FastAPI 后端主入口（所有 API 路由）
├── main.py                    # CLI 命令行 Agent（LangGraph ReAct）
├── tools.py                   # LangGraph Agent 工具定义
│
├── parsers/                   # PDF 解析引擎
│   ├── pypdf_parser.py        #   PyPDF 快速解析
│   ├── mineru_parser.py       #   MinerU 高精度解析
│   ├── metadata_extractor.py  #   LLM 元数据提取
│   └── base.py                #   ParseResult 统一数据结构
│
├── store/                     # 存储层
│   ├── vector_store.py        #   ChromaDB 向量存储
│   ├── bm25_store.py          #   BM25 关键词索引
│   ├── hybrid_retriever.py    #   混合检索器 (Vector + BM25 + RRF)
│   ├── reranker.py            #   LLM 重排序器
│   ├── text_splitter.py       #   文本分块 (800字/100重叠)
│   ├── paper_status_store.py  #   论文阅读状态
│   └── upload_log_store.py    #   上传日志
│
├── rag/                       # RAG 问答核心
│   ├── qa_chain.py            #   问答链（编排所有模块）
│   ├── query_rewriter.py      #   Query 改写（代词消解）
│   ├── conversation_memory.py #   对话记忆（摘要 + Token Budget）
│   ├── graph_retriever.py     #   图谱增强检索
│   ├── session_store.py       #   会话持久化
│   └── annotation_store.py    #   PDF 标注存储
│
├── graph/                     # 知识图谱
│   ├── neo4j_store.py         #   Neo4j 驱动封装
│   └── extractor.py           #   LLM 知识抽取（实体 + 关系）
│
├── memory/                    # 自生长记忆系统
│   ├── memory_store.py        #   记忆存储（ChromaDB + SQLite 双存储）
│   ├── distiller.py           #   问答蒸馏器
│   ├── memory_retriever.py    #   记忆检索 + 注入
│   ├── profile_builder.py     #   用户画像生成
│   ├── knowledge_tree.py      #   知识树（Neo4j 节点掌握度）
│   ├── interest_graph.py      #   用户兴趣图谱（CRUD + 生命周期）
│   ├── interest_distiller.py  #   兴趣蒸馏器（问答 → 图谱节点）
│   ├── interest_retriever.py  #   兴趣检索（注入问答上下文）
│   └── structure_reviewer.py  #   结构审视器（定期 LLM 归纳）
│
├── recommend/                 # 论文推荐
│   ├── semantic_scholar.py    #   Semantic Scholar API 检索
│   └── ccf_mapper.py          #   CCF 等级映射
│
├── auth/                      # 认证
│   ├── jwt_handler.py         #   JWT 签发 / 验证
│   └── user_store.py          #   用户注册 / 登录（bcrypt）
│
├── frontend/                  # Next.js 前端
│   └── src/
│       ├── app/
│       │   ├── library/       #   论文库页面
│       │   ├── chat/          #   AI 对话页面
│       │   ├── knowledge/     #   知识图谱可视化
│       │   ├── memory/        #   记忆 & 兴趣图谱
│       │   ├── discover/      #   论文推荐
│       │   ├── stats/         #   统计面板
│       │   ├── settings/      #   用户设置
│       │   └── login/         #   登录/注册
│       ├── components/
│       │   ├── library/       #   PDF 阅读器 & 标注组件
│       │   ├── layout/        #   导航布局
│       │   └── ui/            #   shadcn/ui 基础组件
│       └── lib/
│           ├── api.ts         #   API Client（authFetch 封装）
│           ├── auth.ts        #   Token 管理
│           └── conversations.ts # 会话管理
│
├── docs/                      # 设计文档
│   ├── self-growing-memory-design.md
│   └── user-interest-graph-design.md
│
├── docker-compose.yml         # 三容器编排
├── Dockerfile.backend         # 后端镜像
├── frontend/Dockerfile        # 前端镜像
├── requirements.txt           # Python 依赖
└── ccf_venues.json            # CCF 会议/期刊等级数据
```

---

## 🔌 API 概览

启动后端后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档。核心接口：

| 方法 | 路径 | 功能 |
|------|------|------|
| `POST` | `/api/auth/register` | 用户注册 |
| `POST` | `/api/auth/login` | 登录获取 JWT |
| `POST` | `/api/papers/upload` | 上传 PDF 论文 |
| `GET` | `/api/papers` | 列出论文库 |
| `DELETE` | `/api/papers/{title}` | 删除论文 |
| `POST` | `/api/chat` | 多轮问答（SSE 流式） |
| `GET` | `/api/sessions` | 会话列表 |
| `GET` | `/api/sessions/{id}/messages` | 会话历史 |
| `GET` | `/api/knowledge/graph` | 知识图谱数据 |
| `GET` | `/api/interest-graph` | 用户兴趣图谱 |
| `GET` | `/api/interest-graph/summary` | 研究方向摘要 |
| `GET` | `/api/interest-graph/stats` | 图谱健康度指标 |
| `POST` | `/api/recommend` | 论文推荐 |
| `GET/POST` | `/api/annotations` | 标注 CRUD |
| `GET` | `/api/stats` | 研究统计 |
| `GET` | `/api/memory/list` | 记忆条目列表 |
| `GET` | `/api/memory/growth-log` | 记忆生长日志 |

---

## 🧪 数据流

### 论文上传流程

```
PDF 文件 → 保存到磁盘 → 全文解析（PyPDF/MinerU）
    → LLM 元数据提取（标题/作者/摘要/venue）
    → 文本分块（800字/100重叠）
    → ChromaDB 向量嵌入 + BM25 索引构建
    → Neo4j 知识抽取（Method/Problem/Concept/Dataset + 关系）
    → 兴趣图谱种子节点（论文关键概念以低权重加入）
```

### 问答流程

```
用户提问 → Query 改写（指代消解）
    → 混合检索（Vector + BM25 + RRF + Rerank）
    → 图谱关系检索（实体匹配 + 邻居关系）
    → 记忆检索（向量相似 + importance 加权）
    → 兴趣上下文（当前方向 Top 节点）
    → 用户画像注入（缓存的自然语言画像）
    → LLM 流式生成回答
    → [异步] 记忆蒸馏 → 写入记忆库
    → [异步] 兴趣蒸馏 → 更新兴趣图谱
    → [异步] 知识树掌握度更新
```

---

## 🐳 Docker 部署

```yaml
# docker-compose.yml 包含三个服务：
services:
  neo4j:       # Neo4j 5 图数据库（可选）
  backend:     # FastAPI 后端（依赖 Neo4j health check）
  frontend:    # Next.js 前端（依赖 Backend）
```

数据持久化卷：
- `neo4j_data` — 图数据库
- `chroma_data` — 向量数据库
- `uploaded_papers` — 用户上传的 PDF 文件
- `sqlite_data` — SQLite 数据库（会话/标注/记忆）

---

## 📝 开发说明

### 命令行模式

除了 Web 界面，PaperMind 还提供基于 **LangGraph ReAct Agent** 的命令行交互模式：

```bash
python main.py
# 支持：上传论文、语义检索、智能问答、列出/删除论文
```

### 支持的 LLM

通过 OpenAI 兼容接口，可接入：

| Provider | BASE_URL | 推荐模型 |
|----------|----------|----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-v4-flash` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Ollama | `http://localhost:11434/v1` | 本地模型 |

### 学术分词器

BM25 模块自研 `tokenize_academic()` 分词器：
- 英文连续串正则保留整词（`FedAvg`、`Non-IID`、`SCAFFOLD` 不被拆开）
- 中文部分 jieba 分词，过滤单字噪声
- 确保学术缩写命中率

---

## 🗺️ Roadmap

- [x] 双数据库 RAG（ChromaDB + Neo4j）
- [x] 混合检索四阶管线（Vector + BM25 + RRF + Rerank）
- [x] 多轮对话 + Token Budget 记忆管理
- [x] LLM 知识图谱自动抽取 + 可视化
- [x] 自生长记忆系统（蒸馏 + 查重合并 + 强化/沉淀）
- [x] 用户研究兴趣图谱（三级层次 + 权重衰减 + 结构审视）
- [x] Semantic Scholar 论文推荐 + CCF 等级
- [x] PDF 在线阅读 + 持久化标注
- [x] Docker Compose 一键部署
- [ ] 多人协作论文批注
- [ ] 论文引用网络分析
- [ ] 导出研究综述草稿
- [ ] 移动端适配

---

## 📜 License

[MIT License](./LICENSE)

---

<p align="center">
  <em>Built with ❤️ for researchers who want an AI that truly understands their work.</em>
</p>
