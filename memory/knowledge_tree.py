"""
领域知识树 - Neo4j 节点掌握状态
在现有知识图谱节点上叠加"掌握状态"（mastery），反映用户对每个概念的探索深度。

薄封装 graph_store：
- update_from_topics()  问答后调用，把蒸馏 topics 映射到 Neo4j 节点并更新状态
- get_tree_overview()   阈值门控 + 掌握状态分布（供前端）

状态迁移（由 graph_store.update_node_mastery 用 Cypher 完成）：
- unexplored → learning:  首次被问及（query_count 1）
- learning → mastered:    被问及 ≥ 3 次

全程 try-except，Neo4j 不可用则 no-op，不影响问答。
"""

import os
from typing import Optional


# 知识树激活阈值（可配置）
MIN_PAPERS = int(os.getenv("MEMORY_KNOWLEDGE_TREE_MIN_PAPERS", "3"))
MIN_MEMORIES = int(os.getenv("MEMORY_KNOWLEDGE_TREE_MIN_MEMORIES", "10"))


class KnowledgeTree:
    """领域知识树：节点掌握状态管理"""

    def __init__(self, graph_store, memory_store=None, vector_store=None):
        self.graph_store = graph_store
        self.memory_store = memory_store
        self.vector_store = vector_store

    def update_from_topics(self, topics: list[str], user_id: str) -> int:
        """
        问答后调用：把蒸馏出的 topics 映射到 Neo4j 节点并更新掌握状态。
        Neo4j 不可用或失败则 no-op，返回 0。
        """
        if not self.graph_store or not getattr(self.graph_store, "available", False):
            return 0
        if not topics or not user_id:
            return 0
        try:
            return self.graph_store.update_node_mastery(topics, user_id=user_id)
        except Exception as e:
            print(f"⚠️ 知识树更新失败: {e}")
            return 0

    def get_tree_overview(self, user_id: str) -> dict:
        """
        返回知识树概览。阈值门控：论文 ≥ MIN_PAPERS 且 记忆 ≥ MIN_MEMORIES 才解锁。
        未解锁返回 {"unlocked": False, ...}；已解锁返回节点列表 + 状态分布。
        """
        try:
            # Neo4j 不可用直接返回未解锁
            if not self.graph_store or not getattr(self.graph_store, "available", False):
                return self._locked_response("知识图谱功能不可用")

            # 阈值门控
            paper_count = self._count_papers(user_id)
            memory_count = self._count_memories(user_id)
            if paper_count < MIN_PAPERS or memory_count < MIN_MEMORIES:
                return {
                    "unlocked": False,
                    "reason": f"上传论文 {paper_count}/{MIN_PAPERS} 篇，积累记忆 {memory_count}/{MIN_MEMORIES} 条后解锁",
                    "paper_count": paper_count,
                    "memory_count": memory_count,
                }

            nodes = self.graph_store.get_knowledge_tree(user_id=user_id)
            summary = {"mastered": 0, "learning": 0, "unexplored": 0}
            for n in nodes:
                mastery = n.get("mastery", "unexplored")
                if mastery in summary:
                    summary[mastery] += 1

            return {
                "unlocked": True,
                "nodes": nodes,
                "summary": summary,
                "total": len(nodes),
            }
        except Exception as e:
            return self._locked_response(f"知识树查询失败: {e}")

    # ================= 辅助方法 =================

    def _count_papers(self, user_id: str) -> int:
        if not self.vector_store:
            return 0
        try:
            return len(self.vector_store.list_papers(user_id=user_id))
        except Exception:
            return 0

    def _count_memories(self, user_id: str) -> int:
        if not self.memory_store:
            return 0
        try:
            return self.memory_store.get_memory_count(user_id)
        except Exception:
            return 0

    def _locked_response(self, reason: str) -> dict:
        return {"unlocked": False, "reason": reason, "paper_count": 0, "memory_count": 0}
