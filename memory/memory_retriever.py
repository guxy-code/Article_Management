"""
记忆检索器 - 同步（问答前调用，无 LLM）
薄封装层：阈值门控 + 调 memory_store.search_memories + 格式化注入文本。

职责分离（方案 A）：
- retrieve()          返回结构化记忆列表（供注入 + 透传给蒸馏器做效果追踪）
- format_for_prompt() 把记忆列表格式化为带引导指令的 prompt 文本块

全程 try-except，失败返回空，绝不影响问答。
"""

import os
from typing import Optional

from memory.memory_store import MemoryStore


# 记忆库 < 该阈值时不注入（避免稀疏数据噪声）
MEMORY_INJECTION_MIN_ITEMS = int(os.getenv("MEMORY_INJECTION_MIN_ITEMS", "5"))

# 注入文本尾部的引导指令：让 LLM 真正利用记忆
_GUIDE_INSTRUCTION = (
    "注意：以上记忆反映了用户此前的研究关注点。如果用户的问题涉及这些已探索的领域，"
    "请在回答中回应用户的已有理解，避免重复解释基础知识。"
)


class MemoryRetriever:
    """从记忆库检索相关记忆并格式化为问答上下文"""

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def retrieve(self, query: str, user_id: str, k: int = 3) -> list[dict]:
        """
        检索与 query 相关的记忆。
        阈值门控：记忆库 < MEMORY_INJECTION_MIN_ITEMS 时返回空列表。
        返回结构化记忆列表 [{"id","knowledge","importance",...}]。
        失败返回空列表。
        """
        try:
            if self.memory_store.get_memory_count(user_id) < MEMORY_INJECTION_MIN_ITEMS:
                return []
            return self.memory_store.search_memories(query, user_id=user_id, k=k)
        except Exception:
            return []

    def format_for_prompt(self, memories: list[dict]) -> str:
        """
        把记忆列表格式化为注入 prompt 的文本块。
        记忆为空返回空字符串。
        """
        if not memories:
            return ""
        lines = ["**相关记忆（用户之前探索过的知识点）：**"]
        for mem in memories:
            knowledge = mem.get("knowledge", "").strip()
            if not knowledge:
                continue
            importance = mem.get("importance", 0.5)
            lines.append(f"• {knowledge} (重要性:{importance:.2f})")

        # 只有标题行说明没有有效记忆
        if len(lines) == 1:
            return ""

        lines.append("")
        lines.append(_GUIDE_INSTRUCTION)
        return "\n".join(lines)
