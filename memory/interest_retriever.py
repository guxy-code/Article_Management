"""
用户兴趣图谱检索器 - 同步（问答前调用，无 LLM）
从用户兴趣图谱中检索与当前问题相关的节点，计算 Interest Score，
序列化为结构化上下文注入 prompt。

设计要点：
- 同步执行，纯 Neo4j 查询 + 内存计算，不调 LLM
- 图谱为空或 Neo4j 不可用 → 返回空字符串（不影响问答）
- 全程 try-except 降级
"""

import re
from datetime import datetime
from typing import Optional

from memory.interest_graph import InterestGraph


# 最少需要多少个活跃节点才开始注入（避免图谱太稀疏时注入噪音）
MIN_NODES_FOR_INJECTION = 3


class InterestRetriever:
    """从用户兴趣图谱检索相关节点并格式化为问答上下文"""

    def __init__(self, interest_graph: InterestGraph):
        self.graph = interest_graph

    def build_context(self, question: str, user_id: str) -> str:
        """
        完整流程：检索相关节点 → 找上层 Field → 找对比关系 → 序列化为注入文本。
        返回格式化的 prompt 上下文字符串，无相关内容时返回空字符串。
        """
        try:
            if not self.graph.available:
                return ""

            # 阈值检查：图谱太小不注入
            active_count = self.graph.count_active_nodes(user_id)
            if active_count < MIN_NODES_FOR_INJECTION:
                return ""

            # 检索相关节点
            related_nodes = self.retrieve(question, user_id)
            if not related_nodes:
                return ""

            return self._format_context(related_nodes, user_id)
        except Exception:
            return ""

    def retrieve(self, question: str, user_id: str, k: int = 5) -> list[dict]:
        """
        从问题中提取关键词，在图谱中模糊匹配，按 Interest Score 排序返回 Top-K。
        """
        try:
            keywords = self._extract_keywords(question)
            if not keywords:
                return []

            # 关键词匹配（取多一些候选再重排）
            candidates = self.graph.search_by_keywords(keywords, user_id, status="active", limit=k * 3)
            if not candidates:
                return []

            # 按 Interest Score 排序
            scored = [(self.compute_interest_score(node), node) for node in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)

            return [node for _, node in scored[:k]]
        except Exception:
            return []

    def compute_interest_score(self, node: dict) -> float:
        """
        综合兴趣分：Recency×0.3 + Frequency×0.3 + Duration×0.2 + Behavior×0.2
        范围 [0, 1.0]
        """
        try:
            now = datetime.now()

            # Recency: 最近触及越近分越高（半衰期 30 天）
            last_seen_str = node.get("last_seen", "")
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    days_since = max((now - last_seen).days, 0)
                except (ValueError, TypeError):
                    days_since = 30
            else:
                days_since = 30
            recency = 0.5 ** (days_since / 30)

            # Frequency: 命中次数归一化
            hit_count = node.get("hit_count", 0) or 0
            frequency = min(hit_count / 10, 1.0)

            # Duration: 关注持续时间（从首次到最近）
            first_seen_str = node.get("first_seen", "")
            if first_seen_str and last_seen_str:
                try:
                    first_seen = datetime.fromisoformat(first_seen_str)
                    last_seen = datetime.fromisoformat(last_seen_str)
                    duration_days = max((last_seen - first_seen).days, 0)
                except (ValueError, TypeError):
                    duration_days = 0
            else:
                duration_days = 0
            duration = min(duration_days / 90, 1.0)

            # Behavior weight
            behavior = node.get("weight", 0.3) or 0.3

            score = recency * 0.3 + frequency * 0.3 + duration * 0.2 + behavior * 0.2
            return round(score, 4)
        except Exception:
            return 0.0

    # ================= 格式化 =================

    def _format_context(self, related_nodes: list[dict], user_id: str) -> str:
        """把检索到的节点序列化为设计文档定义的注入格式"""
        lines = ["**用户研究上下文：**"]

        # 找上层 Field
        fields = set()
        for node in related_nodes:
            ancestors = self.graph.get_ancestors(node["name"], user_id, ancestor_type="Field")
            for a in ancestors:
                fields.add(a.get("name", ""))
        fields.discard("")

        if fields:
            lines.append("研究方向：" + "、".join(sorted(fields)))

        # 相关已有认知
        lines.append("相关已有认知：")
        for node in related_nodes[:5]:
            name = node.get("name", "")
            desc = node.get("description", "")
            if desc:
                lines.append(f"• {name}：{desc}")
            else:
                lines.append(f"• {name}")

        # 对比关系
        node_names = [n["name"] for n in related_nodes]
        comparisons = self.graph.get_comparisons_among(node_names, user_id)
        if comparisons:
            lines.append("用户正在关注的对比：")
            for c in comparisons:
                lines.append(f"• {c['from_name']} vs {c['to_name']}")

        lines.append("")
        lines.append("请基于用户已有认知回答，不重复解释已熟悉的基础概念。")
        return "\n".join(lines)

    # ================= 关键词提取 =================

    def _extract_keywords(self, question: str) -> list[str]:
        """
        从问题中提取关键词用于图谱匹配。
        策略：提取英文术语（连续英文单词）+ 中文关键词（长度>=2 的非停用词片段）。
        """
        keywords = []

        # 1. 提取英文术语（包含大写字母的词、或长度>=3 的纯英文词）
        english_terms = re.findall(r'[A-Za-z][A-Za-z0-9\-_]*[A-Za-z0-9]', question)
        for term in english_terms:
            if len(term) >= 3 or any(c.isupper() for c in term):
                if term.lower() not in ("the", "and", "for", "that", "this", "with", "from", "are", "was", "how", "what", "why"):
                    keywords.append(term)

        # 2. 提取中文关键词（简单：取连续中文字符中长度>=2 的片段）
        chinese_segments = re.findall(r'[\u4e00-\u9fff]{2,}', question)
        # 过滤停用词
        stop_words = {"什么", "怎么", "如何", "为什么", "是不是", "有什么", "可以", "能不能", "请问", "之间", "区别", "关系", "问题"}
        for seg in chinese_segments:
            if seg not in stop_words and len(seg) >= 2:
                keywords.append(seg)

        return keywords[:10]  # 限制数量避免查询过重
