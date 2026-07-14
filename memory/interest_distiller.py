"""
用户兴趣图谱蒸馏器 - 异步
问答结束后，从交互中提取结构化实体+关系，写入用户兴趣图谱。

设计要点：
- 两层过滤：规则过滤（零成本）+ LLM skip 输出
- 异步执行（asyncio.create_task 触发），LLM 用 ainvoke
- Retry once（间隔 2 秒）+ MERGE 幂等写入
- 蒸馏后顺带执行衰减 + 容量检查
- 全程 try-except，任何失败只打日志，绝不影响问答
"""

import os
import json
import asyncio
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from memory.interest_graph import InterestGraph, normalize, DISTILL_WEIGHT, HIT_BOOST, MAX_ACTIVE_NODES


# ---- 配置 ----
RETRY_COUNT = int(os.getenv("INTEREST_GRAPH_DISTILL_RETRY_COUNT", "1"))
RETRY_DELAY = int(os.getenv("INTEREST_GRAPH_DISTILL_RETRY_DELAY", "2"))
TOP_NODES_FOR_PROMPT = int(os.getenv("INTEREST_GRAPH_TOP_NODES_FOR_PROMPT", "20"))
REVIEW_INTERVAL = int(os.getenv("INTEREST_GRAPH_REVIEW_INTERVAL", "20"))

# ---- 规则过滤 ----
_OPERATION_PATTERNS = ["列出", "删除", "上传", "下载", "打开", "关闭", "切换"]
_GREETINGS = ["好的", "谢谢", "明白", "了解", "ok", "OK", "嗯", "行"]

# ---- 蒸馏 Prompt ----
DISTILL_SYSTEM = "你是学术研究兴趣分析专家，从问答中提取用户研究兴趣的结构化信息。只返回 JSON。"

DISTILL_PROMPT = """请分析以下学术问答，提取用户研究兴趣的结构化信息。

规则：
1. 提取 2-5 个核心实体，标注类型（Field / Topic / Entity）
2. 为每个实体提供一句话描述（说明它是什么，而非用户对它了解多少）
3. 标注实体间关系，类型：CONTAINS / RELATES_TO / COMPARES_WITH
4. 为 RELATES_TO 类型的关系提供一句描述（说明具体什么关系）
5. 不要提取过于泛化的词（"机器学习"、"深度学习"），除非确实是用户焦点
6. 如果指的是下方已有节点中的某个实体，请使用完全一致的名称
7. 如果问答不涉及学术研究，输出 {"skip": true}
8. 同时输出一条 knowledge_summary（一句中文概括本次问答的核心知识点）
9. 只输出 JSON

输出格式：
{
  "entities": [
    {"name": "SCAFFOLD", "type": "Entity", "description": "引入 control variate 校正客户端更新方向的联邦学习算法"}
  ],
  "relations": [
    {"from": "SCAFFOLD", "to": "客户端漂移", "type": "RELATES_TO", "description": "通过控制变量校正来解决漂移问题"}
  ],
  "knowledge_summary": "SCAFFOLD 通过 control variate 校正客户端梯度方向来解决联邦学习中的漂移问题",
  "skip": false
}

--- 用户图谱现有核心节点（请尽量对齐已有名称）---
{existing_nodes}

--- 交互内容 ---
用户问题：{question}
AI 回答（前800字）：{answer_truncated}
来源论文：{source_titles}
"""


class InterestDistiller:
    """用户兴趣图谱蒸馏器：从问答中提取实体+关系，写入图谱"""

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
        # 蒸馏成功计数（用于触发结构审视）
        self._distill_count = 0
        # 结构审视器（由外部注入，可选）
        self.structure_reviewer = None

    # ================= 规则过滤 =================

    def should_distill(self, question: str, answer: str) -> bool:
        """第一层规则过滤（零成本）"""
        q = question.strip()
        if len(q) < 10:
            return False
        if "知识库为空" in answer or "未找到相关内容" in answer:
            return False
        if any(q.startswith(p) for p in _OPERATION_PATTERNS) and len(q) < 20:
            return False
        if q in _GREETINGS:
            return False
        return True

    # ================= 主入口 =================

    async def distill_async(
        self,
        question: str,
        answer: str,
        sources: Optional[list[dict]] = None,
        session_id: Optional[str] = None,
        user_id: str = "system",
    ) -> Optional[dict]:
        """
        异步蒸馏：从问答交互提取实体+关系，写入兴趣图谱。
        返回提取结果 dict（含 knowledge_summary），失败返回 None。
        全程 try-except，失败只打日志。
        """
        try:
            # 1. 规则过滤
            if not self.should_distill(question, answer):
                return None

            # 2. 获取现有节点（供 LLM 对齐）
            existing_nodes = self._get_existing_nodes_for_prompt(user_id)

            # 3. 提取来源标题
            source_titles = []
            if sources:
                for s in sources:
                    title = s.get("title")
                    if title and title not in source_titles:
                        source_titles.append(title)

            # 4. 调 LLM（含 retry）
            result = await self._call_llm_with_retry(
                question=question,
                answer=answer[:800],
                source_titles=source_titles,
                existing_nodes=existing_nodes,
            )
            if result is None or result.get("skip"):
                return None

            # 5. 写入图谱
            entities = result.get("entities") or []
            relations = result.get("relations") or []
            if not entities:
                return None

            write_stats = self._write_to_graph(entities, relations, user_id, source="qa_distill")

            # 6. 后置维护（衰减 + 容量）
            self._post_write_maintenance(user_id)

            # 7. 计数（结构审视触发）
            self._distill_count += 1
            if self._distill_count >= REVIEW_INTERVAL:
                self._distill_count = 0
                # 触发结构审视
                if self.structure_reviewer:
                    try:
                        asyncio.create_task(self.structure_reviewer.review_async(user_id))
                    except RuntimeError:
                        pass
                self.graph.log_event(user_id, "review_triggered", {
                    "reason": f"distill_count reached {REVIEW_INTERVAL}"
                }, source="system")

            return result

        except Exception as e:
            print(f"⚠️ 兴趣图谱蒸馏失败: {e}")
            return None

    # ================= LLM 调用 =================

    async def _call_llm_with_retry(
        self,
        question: str,
        answer: str,
        source_titles: list[str],
        existing_nodes: str,
    ) -> Optional[dict]:
        """调 LLM 提取结构化信息，含 retry once"""
        prompt_content = DISTILL_PROMPT.format(
            existing_nodes=existing_nodes,
            question=question,
            answer_truncated=answer,
            source_titles=", ".join(source_titles) if source_titles else "无",
        )
        messages = [
            SystemMessage(content=DISTILL_SYSTEM),
            HumanMessage(content=prompt_content),
        ]

        for attempt in range(1 + RETRY_COUNT):
            try:
                response = await self.llm.ainvoke(messages)
                result = self._parse_json(response.content)
                if result is not None:
                    return result
            except Exception as e:
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                print(f"⚠️ 兴趣蒸馏 LLM 调用最终失败: {e}")
                return None
        return None

    # ================= 写入图谱 =================

    def _write_to_graph(self, entities: list[dict], relations: list[dict], user_id: str, source: str) -> dict:
        """把提取的实体和关系写入兴趣图谱，返回统计"""
        nodes_created = 0
        nodes_updated = 0
        relations_created = 0

        for entity in entities:
            name = normalize(entity.get("name", "").strip())
            if not name:
                continue
            etype = entity.get("type", "Entity")
            if etype not in ("Field", "Topic", "Entity"):
                etype = "Entity"
            description = entity.get("description", "")

            existing = self.graph.find_node(name, user_id)
            if existing:
                # 已存在 → 更新
                updates = {
                    "weight": min((existing.get("weight") or 0) + HIT_BOOST, 1.0),
                    "hit_count": (existing.get("hit_count") or 0) + 1,
                    "last_seen": __import__("datetime").datetime.now().isoformat(),
                }
                # 唤醒 dormant 节点
                if existing.get("status") == "dormant":
                    updates["status"] = "active"
                    updates["weight"] = 0.3
                # Description 更新校验
                if self._should_update_description(existing.get("description", ""), description):
                    updates["prev_description"] = existing.get("description", "")
                    updates["description"] = description
                self.graph.update_node(name, user_id, **updates)
                nodes_updated += 1
                self.graph.log_event(user_id, "node_strengthened", {
                    "node": name, "source": source,
                }, source=source)
            else:
                # 不存在 → 创建
                self.graph.create_node(
                    name=name,
                    type=etype,
                    user_id=user_id,
                    description=description,
                    weight=DISTILL_WEIGHT,
                    hit_count=1,
                )
                nodes_created += 1
                self.graph.log_event(user_id, "node_created", {
                    "node": name, "type": etype, "source": source,
                }, source=source)

        for rel in relations:
            from_name = normalize(rel.get("from", "").strip())
            to_name = normalize(rel.get("to", "").strip())
            rel_type = rel.get("type", "RELATES_TO")
            description = rel.get("description", "")

            if not from_name or not to_name:
                continue

            success = self.graph.create_relation(
                from_name=from_name,
                to_name=to_name,
                rel_type=rel_type,
                user_id=user_id,
                description=description,
                source=source,
            )
            if success:
                relations_created += 1
                self.graph.log_event(user_id, "relation_created", {
                    "from": from_name, "to": to_name, "type": rel_type, "source": source,
                }, source=source)

        return {"nodes_created": nodes_created, "nodes_updated": nodes_updated, "relations_created": relations_created}

    # ================= 后置维护 =================

    def _post_write_maintenance(self, user_id: str):
        """写入后执行衰减 + 容量检查"""
        try:
            self.graph.apply_decay(user_id)
        except Exception:
            pass

        try:
            active_count = self.graph.count_active_nodes(user_id)
            if active_count > MAX_ACTIVE_NODES:
                excess = active_count - int(MAX_ACTIVE_NODES * 0.8)
                self.graph.dormant_lowest_weight(user_id, count=excess)
        except Exception:
            pass

    # ================= 辅助方法 =================

    def _get_existing_nodes_for_prompt(self, user_id: str) -> str:
        """获取 Top-N 活跃节点名列表，供蒸馏 Prompt 使用"""
        try:
            top_nodes = self.graph.get_top_nodes(user_id, limit=TOP_NODES_FOR_PROMPT)
            if not top_nodes:
                return "（暂无）"
            return ", ".join(n["name"] for n in top_nodes)
        except Exception:
            return "（暂无）"

    def _should_update_description(self, old_desc: str, new_desc: str) -> bool:
        """判断是否应该更新描述：长度 + 关键词校验"""
        if not old_desc:
            return bool(new_desc)
        if not new_desc:
            return False
        # 条件 1：新描述明显更长（至少多 20%）
        if len(new_desc) <= len(old_desc) * 1.2:
            return False
        # 条件 2：新描述包含旧描述的部分关键词（避免完全跑偏）
        old_words = set(old_desc.lower().split())
        new_words = set(new_desc.lower().split())
        if old_words and len(old_words & new_words) / len(old_words) < 0.2:
            return False
        return True

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
