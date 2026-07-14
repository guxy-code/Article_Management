"""
用户兴趣图谱结构审视器 - 异步
定期（每 N 次蒸馏后）审视图谱完整性，补充层级关系、合并同义节点、归纳 Field。

设计要点：
- 异步执行（由 interest_distiller 计数触发，或手动 rebuild 端点触发）
- 单次 LLM 调用，输入图谱 dump（name + type + hit_count），输出操作列表
- Token 控制：只传 weight > 0.2 的活跃节点，不传 description 全文
- 全程 try-except，失败只打日志
"""

import os
import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from memory.interest_graph import InterestGraph, normalize


REVIEW_SYSTEM = "你是学术知识图谱结构化专家。请审视用户研究兴趣图谱，检查结构完整性。只返回 JSON。"

REVIEW_PROMPT = """请审视以下用户研究兴趣图谱，检查结构完整性并输出需要执行的操作。

当前图谱节点：
{nodes_dump}

当前图谱关系：
{relations_dump}

请检查并输出需要执行的操作：
1. merge: 应该合并的同义节点对（名称不同但指同一概念）
2. add_contains: 应该补充的层级关系（哪些 Entity/Topic 应归属到哪个 Topic/Field 下）
3. add_field: 应该新建的 Field 节点（如果多个 Topic/Entity 明显属于同一大方向但还没有对应的 Field）
4. add_relation: 应该补充的语义关系（RELATES_TO 或 COMPARES_WITH）

规则：
- 只输出确定性高的操作，不要猜测
- merge 只针对明确的同义词（如 "FedAvg" 和 "Federated Averaging"）
- add_field 只在有 3 个以上明显属于同一方向的节点时才创建
- 每类操作最多 5 个（避免过度调整）
- 如果图谱结构已经完善，可以输出空列表

只输出 JSON：
{{
  "merge": [{{"keep": "保留名称", "remove": "删除名称"}}],
  "add_contains": [{{"parent": "父节点名", "child": "子节点名"}}],
  "add_field": [{{"name": "方向名称", "description": "一句话描述"}}],
  "add_relation": [{{"from": "起点名", "to": "终点名", "type": "RELATES_TO", "description": "关系描述"}}]
}}
"""


class StructureReviewer:
    """用户兴趣图谱结构审视器"""

    def __init__(
        self,
        interest_graph: InterestGraph,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.graph = interest_graph
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    async def review_async(self, user_id: str) -> dict:
        """
        异步审视图谱结构完整性。
        返回执行结果统计 {"merged": N, "contains_added": N, "fields_added": N, "relations_added": N}。
        失败返回空 dict。
        """
        try:
            if not self.graph.available:
                return {}

            # 1. 获取图谱 dump（只取活跃 + weight > 0.2 的节点）
            nodes_dump, relations_dump = self._build_graph_dump(user_id)
            if not nodes_dump:
                return {}

            # 2. 调 LLM
            prompt_content = REVIEW_PROMPT.format(
                nodes_dump=nodes_dump,
                relations_dump=relations_dump,
            )
            messages = [
                SystemMessage(content=REVIEW_SYSTEM),
                HumanMessage(content=prompt_content),
            ]
            response = await self.llm.ainvoke(messages)
            result = self._parse_json(response.content)
            if not result:
                return {}

            # 3. 执行操作
            stats = self._execute_operations(result, user_id)

            # 4. 记录日志
            self.graph.log_event(user_id, "structure_review", {
                "stats": stats,
                "operations": result,
            }, source="structure_review")

            return stats

        except Exception as e:
            print(f"⚠️ 结构审视失败: {e}")
            return {}

    def _build_graph_dump(self, user_id: str) -> tuple[str, str]:
        """构建图谱 dump 文本（控制 token：只传 name + type + hit_count）"""
        try:
            graph_data = self.graph.get_full_interest_graph(user_id, status="active")
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])

            # 只保留 weight > 0.2 的节点（减少 token）
            filtered_nodes = [n for n in nodes if (n.get("weight") or 0) > 0.2]

            if not filtered_nodes:
                return "", ""

            # 限制节点数（最多 80 个，避免 token 爆炸）
            filtered_nodes = sorted(filtered_nodes, key=lambda n: n.get("weight", 0), reverse=True)[:80]
            node_names = {n["name"] for n in filtered_nodes}

            # 节点 dump
            node_lines = []
            for n in filtered_nodes:
                node_lines.append(f"{n.get('name', '')} | {n.get('type', 'Entity')} | hit={n.get('hit_count', 0)}")
            nodes_dump = "\n".join(node_lines)

            # 关系 dump（只保留两端都在 filtered_nodes 中的）
            rel_lines = []
            for e in edges:
                if e.get("source") in node_names and e.get("target") in node_names:
                    rel_lines.append(f"{e['source']} -> {e.get('type', 'RELATES_TO')} -> {e['target']}")
            relations_dump = "\n".join(rel_lines) if rel_lines else "（暂无关系）"

            return nodes_dump, relations_dump
        except Exception:
            return "", ""

    def _execute_operations(self, result: dict, user_id: str) -> dict:
        """执行 LLM 输出的操作列表"""
        stats = {"merged": 0, "contains_added": 0, "fields_added": 0, "relations_added": 0}

        # 1. 合并同义节点
        for merge_op in (result.get("merge") or [])[:5]:
            keep = merge_op.get("keep", "").strip()
            remove = merge_op.get("remove", "").strip()
            if keep and remove:
                success = self.graph.merge_nodes(normalize(keep), normalize(remove), user_id)
                if success:
                    stats["merged"] += 1

        # 2. 新建 Field 节点
        for field_op in (result.get("add_field") or [])[:5]:
            name = normalize(field_op.get("name", "").strip())
            description = field_op.get("description", "")
            if name:
                existing = self.graph.find_node(name, user_id)
                if not existing:
                    self.graph.create_node(name, "Field", user_id, description=description, weight=0.5, hit_count=0)
                    stats["fields_added"] += 1
                elif existing.get("type") != "Field":
                    # 已存在但不是 Field → 升级为 Field
                    self.graph.update_node(name, user_id, type="Field")
                    stats["fields_added"] += 1

        # 3. 补充 CONTAINS 层级关系
        for contains_op in (result.get("add_contains") or [])[:10]:
            parent = normalize(contains_op.get("parent", "").strip())
            child = normalize(contains_op.get("child", "").strip())
            if parent and child:
                success = self.graph.create_relation(
                    parent, child, "CONTAINS", user_id,
                    description="", source="structure_review",
                )
                if success:
                    stats["contains_added"] += 1

        # 4. 补充语义关系
        for rel_op in (result.get("add_relation") or [])[:5]:
            from_name = normalize(rel_op.get("from", "").strip())
            to_name = normalize(rel_op.get("to", "").strip())
            rel_type = rel_op.get("type", "RELATES_TO")
            description = rel_op.get("description", "")
            if from_name and to_name:
                success = self.graph.create_relation(
                    from_name, to_name, rel_type, user_id,
                    description=description, source="structure_review",
                )
                if success:
                    stats["relations_added"] += 1

        return stats

    def _parse_json(self, content: str) -> Optional[dict]:
        """清理 markdown 代码块并解析 JSON"""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except Exception:
            return None
