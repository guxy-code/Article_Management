# Self-Growing Memory — 完整设计文档

> PaperMind 自生长记忆库：从用户交互中主动学习、持续积累、自我生长的记忆系统

---

## 一、背景与动机

当前 PaperMind 是一个**被动检索工具**：用户问，系统从论文中找片段回答。它有三个记忆断层：

| 断层 | 问题 |
|------|------|
| 对话记忆不跨会话 | `conversation_memory.py` 的摘要只存在单个 session 内，删除即丢失 |
| 知识图谱只记论文不记用户 | `extractor.py` 只从论文前 3000 字提取三元组，完全忽略用户的问答行为和关注点 |
| 用户画像是静态的 | `semantic_scholar.py` 只取概念频率 Top-3 做推荐关键词，粒度极粗，不随用户行为生长 |

**目标**：构建一个从用户交互中主动学习、持续积累、自我生长的记忆系统，使系统从"论文检索工具"升级为"了解用户的研究伙伴"。

---

## 二、核心设计原则

1. **只存精华不存全文** — 记忆库不是另一个向量库，是从交互中蒸馏的知识点
2. **有生长也有沉淀** — importance 强化 + 检索排序实现隐式沉淀（重要的浮上来，不重要的自然沉下去）
3. **主动注入而非被动等待** — 记忆必须在问答时被使用，否则没有价值
4. **复用现有架构** — 不重建存储层，在 ChromaDB/Neo4j/SQLite 上扩展
5. **全部建好 + 阈值激活** — 代码一次到位，用数据阈值控制功能激活，不做分期交付返工

---

## 三、总体架构（三层 + 画像缓存）

```
┌──────────────────────────────────────────────────────────┐
│              自生长记忆库 (Self-Growing Memory)              │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  画像层 (User Research Profile)                      │  │
│  │  从知识树+记忆库聚合，异步生成自然语言画像（缓存）     │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  记忆层 (Core Knowledge Memory)                      │  │
│  │  从问答中蒸馏的关键知识点，带重要性分数 + 去重合并     │  │
│  │  认知轨迹作为附属能力（记忆条目天然形成链）           │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │  知识树层 (Domain Knowledge Tree)                    │  │
│  │  唯一事实来源：Neo4j 节点 + mastery/query_count 属性  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
   注入问答上下文         驱动推荐策略          前端 Memory Base 页面
```

**层间关系**：
- 知识树层 = 唯一事实来源（Neo4j 节点状态）
- 画像层 = 从知识树 + 记忆库聚合生成的缓存视图（不独立维护状态）
- 认知轨迹 = 记忆层的附属能力（记忆条目带 `session_id` 和 `prev_memory_id`，天然形成链）

---

## 四、同步/异步边界

| 操作 | 时机 | 同步/异步 | LLM 调用？ |
|------|------|-----------|-----------|
| 记忆检索注入 prompt | 回答前 | **同步** | ❌（ChromaDB 向量查询） |
| 画像注入 prompt | 回答前 | **同步** | ❌（读 SQLite 缓存） |
| 信息蒸馏 | 回答后 | **异步** fire-and-forget | ✅（1 次） |
| 画像重算 | 定期/阈值触发 | **异步** | ✅（1 次/N轮） |
| 知识树状态更新 | 回答后 | **异步** | ❌（Neo4j 属性写入） |

**单轮问答的 LLM 调用次数不增加**（仍然是 Query 改写 + 图谱实体提取 + 主回答生成）。

---

## 五、各层详细设计

### 5.1 记忆层：信息蒸馏

#### 触发条件

每次问答结束后，先经过**两层过滤**：

**第一层：规则过滤（零成本）**

```python
def should_distill(question: str, answer: str) -> bool:
    # 1. 问题太短
    if len(question.strip()) < 10:
        return False
    # 2. AI 回答是空检索的固定话术
    if "知识库为空" in answer or "未找到相关内容" in answer:
        return False
    # 3. 纯操作类问题
    operation_patterns = ["列出", "删除", "上传", "下载", "打开", "关闭", "切换"]
    if any(question.strip().startswith(p) for p in operation_patterns) and len(question) < 20:
        return False
    # 4. 寒暄/确认
    greetings = ["好的", "谢谢", "明白", "了解", "ok", "OK", "嗯", "行"]
    if question.strip() in greetings or len(question.strip()) < 5:
        return False
    return True
```

**第二层：蒸馏 prompt 内置 skip 判断（LLM 兜底）**

#### 蒸馏 Prompt

```
请从以下学术问答交互中提取一条用户关心的关键知识点。

规则：
1. 如果本次问答不涉及学术知识（如纯操作、寒暄、管理指令），输出 {"skip": true}
2. 优先提取用户的理解/假设/关注点，而非 AI 回答的全部内容
   — 如果用户提出了自己的理解（如"我觉得X本质上是Y"），提取这个理解
   — 如果用户在追问某个细节，提取这个细节作为知识点
3. 用一句完整的中文话表述，保留关键英文术语
4. topics 字段列出所有涉及的主题标签（英文术语）
5. 只输出 JSON

示例1：
用户问题："FedAvg怎么减少通信开销？和FedSGD的区别是什么？"
AI回答："FedAvg通过让客户端本地执行多个epoch的SGD后再上传模型参数..."
输出：{"knowledge": "FedAvg通过客户端本地多轮训练减少通信频率，与FedSGD的核心区别在于本地训练轮数", "topics": ["FedAvg", "FedSGD", "通信效率"], "skip": false}

示例2：
用户问题："我觉得SCAFFOLD的control variate本质上就是在做梯度修正，对吗？"
AI回答："不完全是。SCAFFOLD的control variate修正的是客户端更新方向..."
输出：{"knowledge": "用户认为SCAFFOLD的control variate本质是梯度修正，实际修正的是客户端更新方向与全局梯度的偏差", "topics": ["SCAFFOLD", "control variate", "梯度修正"], "skip": false}

--- 交互内容 ---
用户问题：{question}
AI 回答（前800字）：{answer_truncated}
来源论文：{source_titles}
```

#### 蒸馏输出格式

```json
{
  "knowledge": "FedAvg通过客户端本地多轮训练减少通信频率，但Non-IID数据会导致客户端模型漂移",
  "topics": ["FedAvg", "客户端漂移", "通信效率"],
  "skip": false
}
```

**固定产出 1 条记忆**。topics 字段可多标签。

#### 记忆条目数据结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | UUID |
| user_id | str | 用户隔离 |
| knowledge | str | 蒸馏出的知识点（一句完整的话） |
| topics | list[str] | 关联主题标签 |
| source_papers | str | 来源论文标题（JSON 数组，如 `["Paper A", "Paper B"]`） |
| source_session | str | 来源会话 ID |
| prev_memory_id | str \| None | 认知轨迹链：上一条记忆 ID（同会话） |
| importance | float | 重要性分数 0-1 |
| status | str | "active"（不做衰减，不设 fading） |
| created_at | str | 创建时间 |
| last_accessed | str | 最后访问时间 |
| access_count | int | 访问次数 |

#### 重要性打分（极简版）

```python
# 创建时：
importance = 0.5 + 0.2 * min(access_count / 5, 1.0)  # 基础分 + 访问次数加权

# 追问回溯（在 add_memory 时触发）：
# 如果新记忆有 prev_memory_id，说明用户追问了前一个主题
# → 前一条记忆 importance += 0.3（上限 1.0）

# 检索命中时：
# → importance += 0.05（上限 1.0）
```

**has_followup 的时序处理**：蒸馏发生在回答后，此刻无法知道用户是否会追问。因此 `has_followup` 不作为独立字段，而是在下一条记忆创建时**回溯更新**：

```python
# memory_store.py add_memory 方法
def add_memory(self, ..., session_id, prev_memory_id=None):
    # 创建新记忆...
    
    # 回溯：如果存在 prev_memory_id，说明用户追问了
    if prev_memory_id:
        self._boost_importance(prev_memory_id, boost=0.3)
```

#### 衰减机制：不做显式衰减，用检索排序替代

**设计决策**：不对 importance 做时间衰减。理由：
- "用户不再访问某条记忆"有 4 种原因（兴趣转移 / 已掌握 / 暂时不在 / 忘了但仍关心），衰减只对第 1 种正确，准确率仅 25%
- 检索时的复合排序已隐式实现"旧沉新浮"效果
- 消除了定时任务、活跃判断、冻结/解冻等复杂逻辑

**替代方案：检索时复合排序**

```python
# memory_retriever.py 检索排序
for doc, distance in results:
    similarity = 1 - distance  # cosine distance → similarity
    importance = meta.get('importance', 0.5)
    access_count = meta.get('access_count', 0)
    
    # 复合排序：相似度为主，importance 为辅，access_count 加权
    final_score = similarity * 0.7 + importance * 0.2 + min(access_count / 10, 0.1)
```

**importance 只增不减**：
- 初始打分（创建时）
- 每次被检索命中：`importance += 0.05`（上限 1.0）
- 永远不会主动降低

**何时引入衰减**：当记忆量达到万级以上，检索性能或质量下降时，再基于真实数据设计衰减策略。当前阶段不需要。

#### 记忆引用追踪（效果观测）

蒸馏时检查上一轮注入的记忆是否被 AI 回答引用，作为效果观测信号：

```python
# distiller.py
def _was_memory_used(self, answer: str, injected_memories: list[str]) -> bool:
    """检查注入的记忆是否在回答中出现（粗略字符串匹配）"""
    for mem in injected_memories:
        fingerprint = mem[:20]  # 取记忆前 20 字符作为指纹
        if fingerprint in answer:
            return True
    return False
```

记录在 SQLite（`memory_items` 表新增 `times_used` 字段），用于后续观测"记忆注入的有效率"。不阻塞任何流程，纯统计。

#### 推荐引擎关键词来源

推荐引擎从记忆库 topics 频率统计提取关键词（不从画像文本解析）：

```python
# recommend/semantic_scholar.py 升级
def get_recommendation_keywords(graph_store, memory_store=None, user_id="system"):
    # 优先：记忆库 topics 频率统计
    if memory_store:
        top_topics = memory_store.get_top_topics(user_id, limit=5)
        if top_topics:
            return top_topics
    # 回退：Neo4j 概念频率
    freq = graph_store.get_concept_frequency(user_id=user_id)
    return [c["name"] for c in freq[:3]]
```

`memory_store.get_top_topics()` 实现：从 SQLite 查所有活跃记忆的 topics 字段（JSON 数组），展开统计频率，返回 Top-N。

#### 去重合并（两档）

新记忆 N 到来时，向量检索现有记忆中最相似的 Top-1：

| 条件 | 动作 |
|------|------|
| cosine_distance < `MERGE_THRESHOLD` (0.15) | 合并：更新 knowledge（保留更详细的那条），importance = max(O, N) + 0.05 |
| cosine_distance ≥ `MERGE_THRESHOLD` | 独立新增 |

**不做关联档**（关联关系在检索时的利用方式尚不明确，当前复合排序已满足需求）。阈值为可配置常量。

---

### 5.2 知识树层：Neo4j 节点属性扩展

在现有 Neo4j 节点（Method / Problem / Concept / Dataset）上新增属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| mastery | str | "mastered" / "learning" / "unexplored" |
| query_count | int | 被问及的次数 |
| last_queried | str | 最后一次被问及的时间 |

#### 状态迁移规则

```
unexplored → learning:   用户第一次问及（query_count: 0 → 1）
learning → mastered:     被问及 ≥ 3 次（query_count ≥ 3）
mastered → fading:       30天未访问（只影响前端显示，不删除）
```

迁移只依赖 `query_count`，不重复判断追问深度（追问信号已融入记忆层的 importance）。

#### 更新时机

- 问答结束后异步：从蒸馏的 topics 字段提取实体，更新对应节点的 `query_count += 1`、`last_queried = now`
- 论文上传时：新概念初始化为 `mastery = "unexplored"`

---

### 5.3 画像层：异步生成 + 缓存

#### 激活条件

- 首次生成：问答 ≥ 20 轮
- 后续刷新：每新增 10 轮问答 或 每 7 天

#### 输入数据

```
- 用户已上传论文标题列表 + 每篇的 Concept 列表
- 用户所有会话中的 user 消息（去重后）
- 每条记忆的 knowledge + topics + importance（Top 10）
- 标注内容（text + note）的摘要
- 概念频率统计（Top 10）
```

#### 画像生成 Prompt

```
你是一个学术研究分析专家。请根据以下用户行为数据，生成一份用户研究画像。

要求：
1. 核心研究方向：判断用户最关注的领域，标注依据
2. 关注焦点：列出3-5个细分主题，按重要性排序，标注认知深度
   - "深入"：importance ≥ 0.8 的记忆主题
   - "探索中"：importance 0.5-0.8 的记忆主题
   - "浅层"：仅出现在论文中但 importance 较低或未被问及
3. 知识盲区：出现在论文中但从未被问及的概念
4. 认知阶段（从以下固定选项中选一个）：
   - 基础理解（问题集中在"什么是X"）
   - 问题深入（问题集中在"X有什么问题/局限"）
   - 方案对比（问题集中在"A和B的区别/优劣"）
   - 实验验证（问题集中在"效果如何/实验怎么做"）
5. 用自然语言段落输出，不要 JSON，不要 markdown 标题
6. 总长度控制在 200 字以内

--- 用户行为数据 ---
上传论文：{paper_titles}
论文概念统计：{concept_frequency}
问答历史（去重后）：{question_list}
记忆库摘要：{memory_summaries}
标注内容摘要：{annotation_summaries}

--- 用户研究画像 ---
```

#### 输出示例

```
用户核心研究方向：联邦学习（高频出现于上传论文与问答中）
当前关注焦点：
- FedAvg 算法的客户端漂移问题（importance 0.85，深入）
- Non-IID 数据对联邦学习的影响（importance 0.72，探索中）
- SCAFFOLD 与 FedAvg 的通信效率对比（importance 0.45，探索中）
知识盲区：差分隐私（出现在1篇论文中但从未被问及）
认知阶段：方案对比
```

#### 缓存策略

- 缓存在 SQLite `user_profiles` 表
- 问答时直接读缓存字符串，无 LLM 调用
- 生成失败 → 跳过，下次再试

---

## 六、记忆注入问答流程

### 改造后的问答流程

```
用户问题 → Query改写 → 混合检索(向量+BM25+RRF+重排序)
                         ↗ 图谱增强（现有）
                         ↗ ★ 记忆检索: ChromaDB memories 向量检索 Top-3
                         ↗ ★ 画像注入: 读缓存（如有）
                       → LLM 生成（prompt 新增 memory_context + profile_context）
                       → 流式输出
                       → ★ 异步蒸馏（fire-and-forget）
                       → ★ 异步知识树更新
```

### Prompt 改造

在现有 `CONVERSATIONAL_RAG_PROMPT` 中新增两个变量：

```
{profile_context}

{memory_context}

**对话历史：**
{chat_history}

{graph_context}

**检索到的论文片段：**
{context}
```

- `{profile_context}` = 画像文本（如有）或空字符串
- `{memory_context}` = 格式化的相关记忆条目（如有）或空字符串

#### 记忆检索注入格式

```
**相关记忆（用户之前探索过的知识点）：**
• FedAvg通过客户端本地多轮训练减少通信频率，但Non-IID数据会导致客户端模型漂移 (重要性:0.85)
• SCAFFOLD通过控制变量校正客户端更新方向，缓解漂移问题 (重要性:0.72)

注意：以上记忆反映了用户此前的研究关注点。如果用户的问题涉及这些已探索的领域，请在回答中回应用户的已有理解，避免重复解释基础知识。
```

---

## 七、阈值激活机制

所有组件一次性建好，通过数据阈值控制激活：

| 组件 | 激活条件 | 不满足时行为 |
|------|----------|-------------|
| 记忆蒸馏 | 每次问答后都触发（通过过滤后） | — |
| 记忆存储 + 查重合并 | 每次蒸馏都执行 | — |
| 记忆检索注入 | 记忆库 ≥ 5 条 | 跳过，不影响问答 |
| 重要性打分 | 每条记忆创建时 | — |
| 访问计数 + 排序 | 每次检索注入时 | — |
| ~~衰减机制~~ | **已移除** — 用检索复合排序替代 | — |
| 用户画像 | 问答 ≥ 20 轮 | 不注入画像 |
| 知识树掌握状态 | 论文 ≥ 3 篇 且 记忆 ≥ 10 条 | 不显示掌握状态 |
| 认知轨迹 | 同一会话 ≥ 3 个问题 | 不做轨迹连接 |
| 推荐升级 | 画像已生成 | 回退到现有 Top-3 概念逻辑 |

---

## 八、降级方案

参考现有系统的模式（Neo4j 不可用 → 优雅降级）：

```python
# 记忆检索：失败就空字符串
memory_context = ""
try:
    memory_context = self.memory_retriever.retrieve(question, user_id=user_id)
except Exception:
    memory_context = ""

# 画像注入：无画像就跳过
profile = self.profile_builder.get_or_build_profile(user_id)
profile_context = f"**用户研究画像：**\n{profile}" if profile else ""

# 蒸馏：异步失败只打日志
try:
    asyncio.create_task(self.distiller.distill_async(...))
except Exception as e:
    print(f"⚠️ 记忆蒸馏失败: {e}")
```

**原则：记忆功能的任何失败都不应让用户感知到。**

---

## 九、异步蒸馏触发实现

### 流式版（ask_with_session_stream）

```python
yield {"type": "done", "data": full_answer}

# 保存消息（现有逻辑）
self.session_store.add_message(session_id, "user", question)
self.session_store.add_message(session_id, "assistant", full_answer, ...)

# fire-and-forget 蒸馏
import asyncio
asyncio.create_task(self.distiller.distill_async(
    question=question,
    answer=full_answer,
    sources=sources,
    session_id=session_id,
    user_id=user_id,
))
```

### 非流式版（ask_with_session → 改为 async）

```python
# server.py 端点改为 await
result = await qa_chain.ask_with_session(...)

# qa_chain 内部 fire-and-forget
asyncio.create_task(self.distiller.distill_async(...))
return {"answer": answer, "sources": sources, "rewritten_query": rewritten_query}
```

---

## 十、存储方案

### 10.1 ChromaDB

新增 `memories` collection，显式指定 cosine 距离：

```python
self._vectorstore = Chroma(
    persist_directory=MEMORY_PERSIST_DIR,
    embedding_function=self.embeddings,
    collection_name="memories",
    collection_metadata={"hnsw:space": "cosine"},
)
```

**现有 `papers` collection 不动**（已有数据，改距离函数需要重建索引）。

去重阈值（可配置常量）：

```python
MERGE_THRESHOLD = 0.15  # cosine distance < 0.15 → 合并
```

### 10.2 Neo4j

现有节点增加属性（不新增节点类型）：

```cypher
-- Method / Problem / Concept / Dataset 节点新增：
SET n.mastery = "unexplored"
SET n.query_count = 0
SET n.last_queried = null
```

### 10.3 SQLite

新增两张表：

```sql
-- 记忆条目元数据
CREATE TABLE memory_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    knowledge TEXT NOT NULL,
    topics TEXT NOT NULL,          -- JSON array
    source_papers TEXT,           -- JSON array，如 ["Paper A", "Paper B"]
    source_session TEXT,
    prev_memory_id TEXT,           -- 认知轨迹链
    importance REAL DEFAULT 0.5,
    status TEXT DEFAULT 'active',  -- only 'active' (no衰减, no fading)
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    times_used INTEGER DEFAULT 0    -- 被 AI 回答引用的次数（效果追踪）
);

-- 用户画像缓存
CREATE TABLE user_profiles (
    user_id TEXT PRIMARY KEY,
    profile_text TEXT NOT NULL,    -- 自然语言画像
    interaction_count INTEGER,     -- 生成时的问答轮数
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 十一、新增模块结构

```
memory/
├── __init__.py
├── distiller.py           # 蒸馏器（异步，含前置过滤 + LLM 蒸馏）
├── memory_store.py        # 存储（ChromaDB + SQLite，含查重合并 + 追问回溯）
├── memory_retriever.py    # 检索注入（同步，含 access_count 更新 + 复合排序）
├── profile_builder.py     # 画像构建（异步，阈值激活，缓存 SQLite）
├── knowledge_tree.py      # 知识树状态（Neo4j 属性扩展，异步更新）
└── trail_tracker.py       # 认知轨迹（prev_memory_id 赋值 + 阈值激活的轨迹分析）
```

**ID 一致性约束**：SQLite `memory_items.id` 和 ChromaDB document id 必须使用同一个 UUID。删除时两个存储同步操作。

**已知限制**：importance 只增不减，长期使用后所有记忆的 importance 可能趋同（接近 1.0）。但检索排序公式中 similarity 权重为 0.7，保证即使 importance 全趋同，排序仍以语义相关性为主。

---

## 十二、与现有代码的集成点

| 集成点 | 现有文件 | 改造方式 |
|--------|----------|----------|
| 问答结束触发蒸馏 | `rag/qa_chain.py` | 在 `ask_with_session` / `ask_with_session_stream` 中 fire-and-forget |
| 画像 + 记忆注入 prompt | `rag/qa_chain.py` | 新增 `{memory_context}` + `{profile_context}` 变量 |
| `ask_with_session` 改 async | `rag/qa_chain.py` + `server.py` | 方法签名 + 端点 await |
| 论文上传初始化知识树 | `server.py` upload_paper | 上传后标记新概念为 "unexplored" |
| 推荐引擎升级 | `recommend/semantic_scholar.py` | 画像已生成时从记忆库 topics 频率统计获取关键词（`memory_store.get_top_topics()`），替代简单 Top-3 |
| 前端新页面 | `frontend/src/app/memory/page.tsx` | 新建 Memory Base 页面 |
| 侧边栏导航 | `frontend/src/components/layout/` | 新增 Memory Base 入口 |

---

## 十三、前端：Memory Base 页面（Phase B — 后端稳定后单独交付）

> **交付顺序**：后端为 Phase A，前端为 Phase B。Phase A 验收通过（API 稳定、记忆注入生效）后再启动 Phase B。

### 路由

`/memory` — 在侧边栏 Knowledge 和 Statistics 之间

### 侧边栏顺序

```
首页 (Home)
AI Chat
Library
Discover
Knowledge
Memory Base    ← 新增
Statistics
```

### 页面内容

| 区域 | 展示内容 | 数据来源 API |
|------|----------|-------------|
| 用户画像卡片 | 研究方向、关注焦点、盲区、认知阶段 | `GET /api/memory/profile` |
| 记忆列表 | 蒸馏出的知识点列表，按 importance 排序 | `GET /api/memory/items` |
| 知识树概览 | 各概念的掌握状态（mastered/learning/unexplored 分布） | `GET /api/memory/knowledge-tree` |
| 记忆统计 | 总条数、活跃条数、本周新增 | `GET /api/memory/status` |

### 阈值未满足时的展示

- 画像区域：显示"继续使用，系统将逐步了解你的研究方向"
- 知识树：显示"上传更多论文后解锁"
- 记忆列表：如果为空，显示"开始问答后，系统将自动积累知识记忆"

---

## 十四、后端新增 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/memory/status` | GET | 记忆库状态（条数、画像状态等） |
| `/api/memory/items` | GET | 记忆条目列表（分页，按 importance 排序） |
| `/api/memory/items/{id}` | DELETE | 删除某条记忆 |
| `/api/memory/profile` | GET | 获取用户画像文本 |
| `/api/memory/knowledge-tree` | GET | 知识树掌握状态概览 |
| `/api/memory/refresh-profile` | POST | 手动触发画像重算 |

---

## 十五、配置项

```env
# 记忆库阈值（可调）
MEMORY_MERGE_THRESHOLD=0.15
MEMORY_INJECTION_MIN_ITEMS=5
MEMORY_PROFILE_MIN_INTERACTIONS=20
MEMORY_PROFILE_REFRESH_INTERVAL=10
MEMORY_KNOWLEDGE_TREE_MIN_PAPERS=3
MEMORY_KNOWLEDGE_TREE_MIN_MEMORIES=10
MEMORY_TRAIL_MIN_QUESTIONS=3
```

---

## 十六、风险与应对

| 风险 | 应对 |
|------|------|
| 一次性交付工作量大 | 每个模块逻辑独立，可按模块并行开发 |
| 阈值设错 | 阈值为配置项，上线后可调 |
| 未激活功能有隐藏 bug | 每个功能都需测试"阈值未满足"的路径 |
| 画像生成 LLM 调用慢/失败 | 严格异步 + 失败跳过 + 缓存机制 |
| 蒸馏产出质量不稳定 | 两层过滤 + LLM skip 输出 + 后续可人工标注调优 |

---

## 十七、验收标准

1. **核心验收**：用户在会话 A 中问过的知识点，在会话 B 中被系统"记住"并注入回答上下文
2. **画像验收**：问答 20 轮后，画像自动生成，问答回答质量可感知提升
3. **知识树验收**：上传 3+ 篇论文后，Memory Base 页面展示各概念的掌握程度
4. **降级验收**：关闭 Neo4j / 蒸馏失败时，系统行为等同于没有记忆功能，不报错
5. **性能验收**：记忆注入不增加问答首字延迟（同步路径无 LLM 调用）
