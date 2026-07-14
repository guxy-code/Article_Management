"""
用户画像构建器 - 异步生成 + 缓存
从多信号数据聚合生成一段自然语言研究画像，缓存到 SQLite user_profiles 表。
问答时同步读缓存注入 prompt（无 LLM），生成过程严格异步（ainvoke）。

激活条件：
- 首次生成：问答 ≥ MEMORY_PROFILE_MIN_INTERACTIONS 轮
- 刷新：新增 ≥ MEMORY_PROFILE_REFRESH_INTERVAL 轮 或 距上次 > 7 天

全程 try-except，失败跳过，绝不影响问答。
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from memory.memory_store import MemoryStore


# 激活/刷新阈值（可配置）
MIN_INTERACTIONS = int(os.getenv("MEMORY_PROFILE_MIN_INTERACTIONS", "20"))
REFRESH_INTERVAL = int(os.getenv("MEMORY_PROFILE_REFRESH_INTERVAL", "10"))
REFRESH_DAYS = 7


PROFILE_PROMPT = """你是一个学术研究分析专家。请根据以下用户行为数据，生成一份用户研究画像。

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
{data}

--- 用户研究画像 ---
"""


class ProfileBuilder:
    """用户研究画像构建器"""

    def __init__(
        self,
        memory_store: MemoryStore,
        session_store=None,
        graph_store=None,
        vector_store=None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.memory_store = memory_store
        self.session_store = session_store
        self.graph_store = graph_store
        self.vector_store = vector_store
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    # ================= 读取（同步，供问答注入） =================

    def get_cached_profile_text(self, user_id: str) -> Optional[str]:
        """同步读缓存画像文本，不存在返回 None。失败返回 None。"""
        try:
            cached = self.memory_store.get_cached_profile(user_id)
            return cached["profile_text"] if cached else None
        except Exception:
            return None

    def should_refresh(self, user_id: str) -> bool:
        """判断是否需要（重新）生成画像"""
        try:
            interaction_count = self._count_interactions(user_id)
            if interaction_count < MIN_INTERACTIONS:
                return False

            cached = self.memory_store.get_cached_profile(user_id)
            if not cached:
                return True  # 达到阈值但没画像 → 首次生成

            # 新增问答轮数 ≥ REFRESH_INTERVAL
            last_count = cached.get("interaction_count", 0) or 0
            if interaction_count - last_count >= REFRESH_INTERVAL:
                return True

            # 距上次更新 > REFRESH_DAYS 天
            updated_at = cached.get("updated_at")
            if updated_at:
                try:
                    last_time = datetime.fromisoformat(updated_at)
                    if datetime.now() - last_time > timedelta(days=REFRESH_DAYS):
                        return True
                except ValueError:
                    pass
            return False
        except Exception:
            return False

    # ================= 生成（异步） =================

    async def build_profile_async(self, user_id: str):
        """异步生成画像并写入缓存。全程 try-except，失败只打日志。"""
        try:
            interaction_count = self._count_interactions(user_id)
            if interaction_count < MIN_INTERACTIONS:
                return

            data = self._collect_signals(user_id)
            if not data.strip():
                return

            messages = [
                SystemMessage(content="你是学术研究分析专家，根据用户行为数据生成研究画像。"),
                HumanMessage(content=PROFILE_PROMPT.format(data=data)),
            ]
            response = await self.llm.ainvoke(messages)
            profile_text = (response.content or "").strip()
            if not profile_text:
                return

            self.memory_store.save_profile(user_id, profile_text, interaction_count)
        except Exception as e:
            print(f"⚠️ 画像生成失败: {e}")

    # ================= 辅助方法 =================

    def _count_interactions(self, user_id: str) -> int:
        """统计问答轮数（user 提问数）"""
        if not self.session_store:
            return 0
        try:
            return self.session_store.count_user_messages(user_id, role="user")
        except Exception:
            return 0

    def _collect_signals(self, user_id: str) -> str:
        """收集多信号数据快照，拼成一段文本作为 LLM 输入"""
        parts = []

        # 1. 记忆库 Top-10（knowledge + topics + importance）
        try:
            memories = self.memory_store.list_memories(user_id, limit=10)
            if memories:
                mem_lines = [
                    f"- {m['knowledge']} (importance={m['importance']:.2f}, topics={', '.join(m.get('topics', []))})"
                    for m in memories
                ]
                parts.append("记忆库（用户已探索的知识点）：\n" + "\n".join(mem_lines))
        except Exception:
            pass

        # 2. topics 频率（Top-10）
        try:
            top_topics = self.memory_store.get_top_topics(user_id, limit=10)
            if top_topics:
                parts.append("高频主题：" + "、".join(top_topics))
        except Exception:
            pass

        # 3. 最近问答历史（去重）
        if self.session_store:
            try:
                questions = self.session_store.get_user_questions(user_id, limit=30)
                if questions:
                    q_lines = [f"- {q}" for q in questions[:20]]
                    parts.append("最近问答历史：\n" + "\n".join(q_lines))
            except Exception:
                pass

        # 4. 概念频率（graph_store，加分项）
        if self.graph_store:
            try:
                freq = self.graph_store.get_concept_frequency(user_id=user_id)
                if freq:
                    concept_lines = [f"{c['name']}({c['count']}篇)" for c in freq[:10]]
                    parts.append("论文概念统计：" + "、".join(concept_lines))
            except Exception:
                pass

        # 5. 论文标题（vector_store，加分项）
        if self.vector_store:
            try:
                titles = self.vector_store.list_papers(user_id=user_id)
                if titles:
                    parts.append("已上传论文：" + "、".join(f"《{t}》" for t in titles[:15]))
            except Exception:
                pass

        return "\n\n".join(parts)
