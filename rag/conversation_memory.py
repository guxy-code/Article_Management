"""
对话记忆管理模块
负责历史格式化、Token Budget 分配、摘要生成。
"""

import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


SUMMARY_PROMPT_TEMPLATE = """请用 3-5 句话概括以下学术对话的主要内容，包括讨论了哪些论文/方法、用户关心的核心问题。

对话内容：
{conversation}

摘要："""


class ConversationMemory:
    """对话记忆管理器"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )
        self.summary_prompt = ChatPromptTemplate.from_template(SUMMARY_PROMPT_TEMPLATE)
        self.summary_chain = self.summary_prompt | self.llm | StrOutputParser()

    def format_for_rewrite(self, messages: list[dict], max_turns: int = 2) -> str:
        """
        为 Query 改写准备的轻量上下文。
        只取最近 max_turns 轮（每轮 user+assistant），assistant 截断到 150 字。
        """
        if not messages:
            return ""

        # 取最近 max_turns * 2 条消息
        recent = messages[-(max_turns * 2):]
        parts = []
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            if msg["role"] == "assistant":
                content = self._truncate(content, 150)
            parts.append(f"{role_label}: {content}")

        return "\n".join(parts)

    def format_for_prompt(self, messages: list[dict], summary: str,
                          budget_chars: int) -> str:
        """
        组装给 LLM 看的历史上下文。

        策略：
        1. 如果有 summary，先放 summary
        2. 从最后一条往前，逐条加入消息，直到超出 budget
        3. assistant 消息截断到 300 字
        4. user 消息保留完整
        """
        parts = []
        used_chars = 0

        # 摘要部分
        if summary:
            summary_text = f"[之前的对话摘要] {summary}"
            summary_chars = len(summary_text)
            if summary_chars < budget_chars * 0.4:
                parts.append(summary_text)
                used_chars += summary_chars

        # 从最近往回取消息
        remaining_budget = budget_chars - used_chars
        recent_parts = []

        for msg in reversed(messages):
            role_label = "用户" if msg["role"] == "user" else "助手"
            content = msg["content"]
            if msg["role"] == "assistant":
                content = self._truncate(content, 300)

            line = f"{role_label}: {content}"
            if len(line) > remaining_budget:
                break

            recent_parts.insert(0, line)
            remaining_budget -= len(line)

        parts.extend(recent_parts)

        return "\n".join(parts) if parts else ""

    def calculate_budget(self, chunks_text: str, max_total_chars: int = 4000) -> dict:
        """
        动态分配字符预算。

        分配优先级：
        - 检索 chunks：最高优先，全部保留（不在此 budget 内）
        - 历史部分：用 max_total_chars 减去一些 buffer

        Args:
            chunks_text: 检索到的论文片段文本
            max_total_chars: 历史部分的最大字符预算

        Returns:
            {"history_budget": int}
        """
        # chunks 越长，给历史的空间越小
        chunks_len = len(chunks_text)
        if chunks_len > 5000:
            history_budget = min(max_total_chars, 2000)
        elif chunks_len > 3000:
            history_budget = min(max_total_chars, 3000)
        else:
            history_budget = max_total_chars

        return {"history_budget": history_budget}

    def should_update_summary(self, message_count: int) -> bool:
        """每 3 轮（6条消息）触发一次摘要更新"""
        return message_count > 0 and message_count % 6 == 0

    def generate_summary(self, messages: list[dict]) -> str:
        """调用 LLM 生成对话摘要"""
        if not messages:
            return ""

        # 格式化对话用于摘要
        parts = []
        for msg in messages:
            role_label = "用户" if msg["role"] == "user" else "助手"
            content = self._truncate(msg["content"], 200)
            parts.append(f"{role_label}: {content}")

        conversation_text = "\n".join(parts)

        # 如果对话太长，只取前后部分
        if len(conversation_text) > 3000:
            conversation_text = conversation_text[:1500] + "\n...\n" + conversation_text[-1500:]

        try:
            summary = self.summary_chain.invoke({"conversation": conversation_text})
            return summary.strip()
        except Exception:
            return ""

    def _truncate(self, text: str, max_chars: int) -> str:
        """截断文本，保留开头"""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."
