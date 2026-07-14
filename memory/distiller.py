"""
记忆蒸馏器 - 异步
问答结束后，从交互中提取一条用户关心的关键知识点，写入记忆库。

设计要点：
- 两层过滤：规则过滤（零成本）+ LLM skip 输出
- 异步执行（asyncio.create_task 触发），LLM 用 ainvoke 避免阻塞 event loop
- 全程 try-except，任何失败只打日志，绝不影响问答
- 效果追踪：检查上一轮注入的记忆是否被本次回答引用
"""

import os
import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from memory.memory_store import MemoryStore


DISTILL_PROMPT = """请从以下学术问答交互中提取一条用户关心的关键知识点。

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
"""

# 规则过滤：操作类指令前缀
_OPERATION_PATTERNS = ["列出", "删除", "上传", "下载", "打开", "关闭", "切换"]
# 规则过滤：寒暄/确认
_GREETINGS = ["好的", "谢谢", "明白", "了解", "ok", "OK", "嗯", "行"]


class MemoryDistiller:
    """从问答交互中蒸馏记忆"""

    def __init__(
        self,
        memory_store: MemoryStore,
        knowledge_tree=None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.memory_store = memory_store
        self.knowledge_tree = knowledge_tree  # 可选，问答后更新知识树掌握状态
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    # ================= 规则过滤 =================

    def should_distill(self, question: str, answer: str) -> bool:
        """第一层规则过滤（零成本），过滤明显无价值的问答"""
        q = question.strip()
        # 1. 问题太短
        if len(q) < 10:
            return False
        # 2. AI 回答是空检索的固定话术
        if "知识库为空" in answer or "未找到相关内容" in answer:
            return False
        # 3. 纯操作类短指令
        if any(q.startswith(p) for p in _OPERATION_PATTERNS) and len(q) < 20:
            return False
        # 4. 寒暄/确认
        if q in _GREETINGS:
            return False
        return True

    # ================= 主流程 =================

    async def distill_async(
        self,
        question: str,
        answer: str,
        sources: Optional[list[dict]] = None,
        session_id: Optional[str] = None,
        user_id: str = "system",
        injected_memories: Optional[list[dict]] = None,
    ):
        """
        异步蒸馏：从问答交互提取一条记忆并写入记忆库。
        全程 try-except，失败只打日志，不影响问答。

        Args:
            injected_memories: 本轮注入 prompt 的记忆列表 [{"id","knowledge",...}]，
                               用于效果追踪（是否被回答引用）
        """
        try:
            # 效果追踪：上一轮注入的记忆是否被本次回答引用
            self._track_memory_usage(answer, injected_memories)

            # 规则过滤
            if not self.should_distill(question, answer):
                return

            # 截断 answer，提取来源标题
            answer_truncated = answer[:800]
            source_titles = []
            if sources:
                for s in sources:
                    title = s.get("title")
                    if title and title not in source_titles:
                        source_titles.append(title)

            # 调 LLM（异步，不阻塞 event loop）
            content = (
                f"用户问题：{question}\n"
                f"AI 回答（前800字）：{answer_truncated}\n"
                f"来源论文：{', '.join(source_titles) if source_titles else '无'}"
            )
            messages = [
                SystemMessage(content="你是学术知识蒸馏助手，从问答中提取用户关心的知识点。只返回 JSON。"),
                HumanMessage(content=DISTILL_PROMPT + content),
            ]
            response = await self.llm.ainvoke(messages)

            # 解析 JSON
            result = self._parse_json(response.content)
            if result is None or result.get("skip"):
                return

            knowledge = (result.get("knowledge") or "").strip()
            if not knowledge:
                return
            topics = result.get("topics") or []

            # 查同会话上一条记忆（认知轨迹链）
            prev_memory_id = self.memory_store.get_last_memory_in_session(session_id)

            # 写入记忆库
            self.memory_store.add_memory(
                knowledge=knowledge,
                user_id=user_id,
                topics=topics,
                source_papers=source_titles,
                source_session=session_id,
                prev_memory_id=prev_memory_id,
            )

            # 知识树：把 topics 映射到 Neo4j 节点更新掌握状态（Neo4j 不可用则 no-op）
            if self.knowledge_tree and topics:
                try:
                    self.knowledge_tree.update_from_topics(topics, user_id)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ 记忆蒸馏失败: {e}")

    # ================= 辅助方法 =================

    def _track_memory_usage(self, answer: str, injected_memories: Optional[list[dict]]):
        """检查注入的记忆是否被回答引用（前 20 字符指纹匹配），命中则 times_used +1"""
        if not injected_memories:
            return
        for mem in injected_memories:
            knowledge = mem.get("knowledge", "")
            memory_id = mem.get("id")
            if not knowledge or not memory_id:
                continue
            fingerprint = knowledge[:20]
            if fingerprint and fingerprint in answer:
                try:
                    self.memory_store.mark_memory_used(memory_id)
                except Exception:
                    pass

    def _parse_json(self, content: str) -> Optional[dict]:
        """清理 markdown 代码块并解析 JSON，失败返回 None"""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except Exception:
            return None
