"""
图谱增强检索模块
从用户问题中提取实体，查询 Neo4j 获取结构化关系知识。
"""

import os
import json
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from graph.neo4j_store import GraphStore


ENTITY_EXTRACT_PROMPT = """从用户问题中提取可能在知识图谱中存在的实体名称。
这些实体可能是：论文标题、方法名、算法名、概念、问题、数据集名。

只返回 JSON，格式：
{"entities": ["entity1", "entity2"], "is_relational": true/false}

is_relational 为 true 表示用户在问关系性问题（比如"A和B有什么关系"、"A改进了什么"、"哪些方法解决X"）。
is_relational 为 false 表示用户在问内容性问题（比如"这篇论文讲了什么"、"解释一下X方法"）。

用户问题："""


class GraphRetriever:
    """从知识图谱中检索结构化关系知识"""

    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def retrieve(self, question: str, user_id: Optional[str] = None) -> str:
        """
        从问题中提取实体，查询图谱，返回格式化的关系知识字符串。
        如果没有相关图谱知识，返回空字符串。
        """
        # 如果 Neo4j 不可用，直接跳过，避免浪费 LLM 调用
        if not self.graph_store.available:
            return ""

        # Step 1: 提取实体和判断问题类型
        extraction = self._extract_entities(question)
        entities = extraction.get("entities", [])
        is_relational = extraction.get("is_relational", False)

        if not entities:
            return ""

        # Step 2: 查询图谱
        all_triples = []

        if len(entities) >= 2 and is_relational:
            path = self.graph_store.query_path(entities[0], entities[1], user_id=user_id)
            if path:
                all_triples.extend(path)

        for entity in entities[:3]:
            triples = self.graph_store.query_related(entity, user_id=user_id)
            all_triples.extend(triples)

        if not all_triples:
            return ""

        # Step 3: 去重并格式化
        seen = set()
        unique_triples = []
        for t in all_triples:
            if "subject" in t:
                key = f"{t['subject']}-{t['relation']}-{t['object']}"
            else:
                key = f"{t['source']}-{t['relation']}-{t['target']}"
            if key not in seen:
                seen.add(key)
                unique_triples.append(t)

        lines = ["【知识图谱关系】"]
        for t in unique_triples[:10]:
            if "subject" in t:
                lines.append(f"• {t['subject']} --[{t['relation']}]--> {t['object']}")
            else:
                lines.append(f"• {t['source']} --[{t['relation']}]--> {t['target']}")

        return "\n".join(lines)

    def _extract_entities(self, question: str) -> dict:
        """用 LLM 从问题中提取实体"""
        messages = [
            SystemMessage(content="你是实体提取助手，从问题中提取知识图谱实体。只返回 JSON。"),
            HumanMessage(content=ENTITY_EXTRACT_PROMPT + question),
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except Exception:
            return {"entities": [], "is_relational": False}
