"""
用户研究兴趣图谱 - 存储层
Neo4j UserTopic 节点/关系的完整 CRUD + 生命周期管理 + 日志 + 健康度指标。

设计原则：
- 所有 Neo4j 写入使用 MERGE 语义（幂等）
- 全程 try-except，Neo4j 不可用时优雅降级
- 节点以 (name, user_id) 联合唯一
- 软删除：status="deleted"，30 天后物理清理
- 日志存 SQLite interest_graph_log 表
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Optional


# ---- 配置 ----
DB_PATH = os.getenv("DB_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "sessions.db"
)

SEED_WEIGHT = float(os.getenv("INTEREST_GRAPH_SEED_WEIGHT", "0.1"))
DISTILL_WEIGHT = float(os.getenv("INTEREST_GRAPH_DISTILL_WEIGHT", "0.3"))
HIT_BOOST = float(os.getenv("INTEREST_GRAPH_HIT_BOOST", "0.1"))
DECAY_START_DAYS = int(os.getenv("INTEREST_GRAPH_DECAY_START_DAYS", "60"))
DORMANT_DAYS = int(os.getenv("INTEREST_GRAPH_DORMANT_DAYS", "90"))
DORMANT_WEIGHT_THRESHOLD = float(os.getenv("INTEREST_GRAPH_DORMANT_WEIGHT_THRESHOLD", "0.1"))
MAX_ACTIVE_NODES = int(os.getenv("INTEREST_GRAPH_MAX_ACTIVE_NODES", "300"))
SOFT_DELETE_DAYS = int(os.getenv("INTEREST_GRAPH_SOFT_DELETE_DAYS", "30"))
PHYSICAL_CLEANUP_DAYS = int(os.getenv("INTEREST_GRAPH_PHYSICAL_CLEANUP_DAYS", "180"))
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("INTEREST_GRAPH_LOW_CONFIDENCE_THRESHOLD", "0.3"))

# ---- 实体名标准化 ----
ALIAS_MAP = {
    "FL": "Federated Learning",
    "DP": "Differential Privacy",
    "SGD": "Stochastic Gradient Descent",
    "GAN": "Generative Adversarial Network",
    "CNN": "Convolutional Neural Network",
    "RNN": "Recurrent Neural Network",
    "NLP": "Natural Language Processing",
    "RL": "Reinforcement Learning",
}

_SUFFIX_LIST = ["算法", "方法", "技术", "模型", "framework", "algorithm", "method", "model"]


def normalize(name: str) -> str:
    """实体名标准化：缩写映射 + 去后缀 + 保持原始大小写"""
    name = name.strip()
    if not name:
        return name

    # 1. 如果是已知缩写的展开形式，统一为缩写
    for abbr, full in ALIAS_MAP.items():
        if name.lower() == full.lower():
            return abbr

    # 2. 去多余后缀
    for suffix in _SUFFIX_LIST:
        if name.lower().endswith(suffix.lower()) and len(name) > len(suffix) + 2:
            name = name[: -(len(suffix))].strip()
            break

    return name


class InterestGraph:
    """用户研究兴趣图谱：Neo4j UserTopic CRUD + 生命周期 + 日志"""

    def __init__(self, graph_store=None, db_path: str = DB_PATH):
        """
        Args:
            graph_store: GraphStore 实例（复用已有 Neo4j 连接）
            db_path: SQLite 数据库路径（存日志）
        """
        self.graph_store = graph_store
        self.db_path = db_path
        self._available = bool(graph_store and getattr(graph_store, "available", False))
        self._init_log_table()

    @property
    def available(self) -> bool:
        return self._available

    # ================= Schema =================

    def init_schema(self):
        """创建 UserTopic 的 NODE KEY 约束"""
        if not self._available:
            return
        try:
            with self.graph_store.driver.session() as session:
                session.run(
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:UserTopic) "
                    "REQUIRE (t.name, t.user_id) IS NODE KEY"
                )
        except Exception as e:
            print(f"⚠️ UserTopic 约束创建失败（可能已存在）: {e}")

    # ================= 节点 CRUD =================

    def create_node(
        self,
        name: str,
        type: str,
        user_id: str,
        description: str = "",
        weight: float = DISTILL_WEIGHT,
        hit_count: int = 1,
    ) -> Optional[str]:
        """
        创建 UserTopic 节点（MERGE 幂等）。
        返回节点内部 ID（str），失败返回 None。
        """
        if not self._available:
            return None
        now = datetime.now().isoformat()
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MERGE (t:UserTopic {name: $name, user_id: $user_id})
                    ON CREATE SET
                        t.type = $type,
                        t.description = $description,
                        t.weight = $weight,
                        t.hit_count = $hit_count,
                        t.first_seen = $now,
                        t.last_seen = $now,
                        t.status = 'active'
                    ON MATCH SET
                        t.weight = CASE WHEN t.weight + $boost > 1.0 THEN 1.0
                                        ELSE t.weight + $boost END,
                        t.hit_count = t.hit_count + 1,
                        t.last_seen = $now,
                        t.status = CASE WHEN t.status = 'dormant' THEN 'active' ELSE t.status END
                    RETURN elementId(t) AS eid
                    """,
                    name=name,
                    user_id=user_id,
                    type=type,
                    description=description,
                    weight=weight,
                    hit_count=hit_count,
                    now=now,
                    boost=HIT_BOOST,
                )
                record = result.single()
                return record["eid"] if record else None
        except Exception as e:
            print(f"⚠️ 创建 UserTopic 节点失败: {e}")
            return None

    def find_node(self, name: str, user_id: str) -> Optional[dict]:
        """按 name + user_id 精确查找节点，返回属性 dict 或 None"""
        if not self._available:
            return None
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:UserTopic {name: $name, user_id: $user_id})
                    RETURN elementId(t) AS eid, properties(t) AS props
                    """,
                    name=name,
                    user_id=user_id,
                )
                record = result.single()
                if not record:
                    return None
                props = dict(record["props"])
                props["_eid"] = record["eid"]
                return props
        except Exception:
            return None

    def update_node(self, name: str, user_id: str, **props) -> bool:
        """更新节点属性。支持 weight/hit_count/last_seen/status/description/prev_description"""
        if not self._available or not props:
            return False
        set_clauses = []
        params = {"name": name, "user_id": user_id}
        for key, value in props.items():
            safe_key = f"p_{key}"
            set_clauses.append(f"t.{key} = ${safe_key}")
            params[safe_key] = value
        cypher = (
            "MATCH (t:UserTopic {name: $name, user_id: $user_id}) "
            f"SET {', '.join(set_clauses)} "
            "RETURN t.name AS n"
        )
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(cypher, **params)
                return result.single() is not None
        except Exception as e:
            print(f"⚠️ 更新节点失败: {e}")
            return False

    def soft_delete_node(self, name: str, user_id: str) -> bool:
        """软删除：status → deleted，记录 deleted_at"""
        now = datetime.now().isoformat()
        success = self.update_node(name, user_id, status="deleted", deleted_at=now)
        if success:
            self.log_event(user_id, "node_deleted", {"node": name}, source="user_action")
        return success

    def restore_node(self, name: str, user_id: str) -> bool:
        """恢复软删除节点（30 天内）"""
        node = self.find_node(name, user_id)
        if not node or node.get("status") != "deleted":
            return False
        deleted_at = node.get("deleted_at")
        if deleted_at:
            try:
                dt = datetime.fromisoformat(deleted_at)
                if (datetime.now() - dt).days > SOFT_DELETE_DAYS:
                    return False  # 超过恢复期
            except ValueError:
                pass
        success = self.update_node(name, user_id, status="active", deleted_at=None)
        if success:
            self.log_event(user_id, "node_restored", {"node": name}, source="user_action")
        return success

    def count_active_nodes(self, user_id: str) -> int:
        """统计活跃节点数"""
        if not self._available:
            return 0
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    "MATCH (t:UserTopic {user_id: $user_id, status: 'active'}) RETURN count(t) AS c",
                    user_id=user_id,
                )
                record = result.single()
                return record["c"] if record else 0
        except Exception:
            return 0

    # ================= 关系 CRUD =================

    def create_relation(
        self,
        from_name: str,
        to_name: str,
        rel_type: str,
        user_id: str,
        description: str = "",
        weight: float = 0.3,
        confidence: float = 0.5,
        source: str = "qa_distill",
    ) -> bool:
        """创建关系（MERGE 幂等）。rel_type: CONTAINS / RELATES_TO / COMPARES_WITH"""
        if not self._available:
            return False
        now = datetime.now().isoformat()
        # 动态关系类型需要用 APOC 或拼接 Cypher（Neo4j 不支持参数化关系类型）
        if rel_type not in ("CONTAINS", "RELATES_TO", "COMPARES_WITH"):
            rel_type = "RELATES_TO"
        try:
            with self.graph_store.driver.session() as session:
                cypher = f"""
                    MATCH (a:UserTopic {{name: $from_name, user_id: $user_id}})
                    MATCH (b:UserTopic {{name: $to_name, user_id: $user_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    ON CREATE SET
                        r.description = $description,
                        r.weight = $weight,
                        r.confidence = $confidence,
                        r.support_count = 1,
                        r.source = $source,
                        r.created_at = $now,
                        r.last_seen = $now
                    ON MATCH SET
                        r.weight = CASE WHEN r.weight + {HIT_BOOST} > 1.0 THEN 1.0
                                        ELSE r.weight + {HIT_BOOST} END,
                        r.confidence = CASE WHEN r.confidence + 0.15 > 1.0 THEN 1.0
                                            ELSE r.confidence + 0.15 END,
                        r.support_count = r.support_count + 1,
                        r.last_seen = $now
                    RETURN type(r) AS rt
                """
                result = session.run(
                    cypher,
                    from_name=from_name,
                    to_name=to_name,
                    user_id=user_id,
                    description=description,
                    weight=weight,
                    confidence=confidence,
                    source=source,
                    now=now,
                )
                return result.single() is not None
        except Exception as e:
            print(f"⚠️ 创建关系失败: {e}")
            return False

    def find_relation(self, from_name: str, to_name: str, rel_type: str, user_id: str) -> Optional[dict]:
        """查找两节点间指定类型的关系"""
        if not self._available:
            return None
        if rel_type not in ("CONTAINS", "RELATES_TO", "COMPARES_WITH"):
            rel_type = "RELATES_TO"
        try:
            with self.graph_store.driver.session() as session:
                cypher = f"""
                    MATCH (a:UserTopic {{name: $from_name, user_id: $user_id}})
                          -[r:{rel_type}]->
                          (b:UserTopic {{name: $to_name, user_id: $user_id}})
                    RETURN properties(r) AS props
                """
                result = session.run(cypher, from_name=from_name, to_name=to_name, user_id=user_id)
                record = result.single()
                return dict(record["props"]) if record else None
        except Exception:
            return None

    def transfer_relations(self, from_name: str, to_name: str, user_id: str):
        """把 from_name 节点的所有关系迁移到 to_name 节点（合并用）"""
        if not self._available:
            return
        try:
            with self.graph_store.driver.session() as session:
                # 迁移出边
                session.run(
                    """
                    MATCH (old:UserTopic {name: $from_name, user_id: $user_id})-[r]->(target)
                    WHERE target.name <> $to_name
                    MATCH (new:UserTopic {name: $to_name, user_id: $user_id})
                    WITH new, target, type(r) AS rtype, properties(r) AS rprops, r
                    DELETE r
                    WITH new, target, rtype, rprops
                    CALL apoc.create.relationship(new, rtype, rprops, target) YIELD rel
                    RETURN count(rel)
                    """,
                    from_name=from_name,
                    to_name=to_name,
                    user_id=user_id,
                )
                # 迁移入边
                session.run(
                    """
                    MATCH (source)-[r]->(old:UserTopic {name: $from_name, user_id: $user_id})
                    WHERE source.name <> $to_name
                    MATCH (new:UserTopic {name: $to_name, user_id: $user_id})
                    WITH source, new, type(r) AS rtype, properties(r) AS rprops, r
                    DELETE r
                    WITH source, new, rtype, rprops
                    CALL apoc.create.relationship(source, rtype, rprops, new) YIELD rel
                    RETURN count(rel)
                    """,
                    from_name=from_name,
                    to_name=to_name,
                    user_id=user_id,
                )
        except Exception as e:
            # APOC 不可用时用备选方案（只处理已知关系类型）
            print(f"⚠️ 关系迁移失败（可能缺少 APOC 插件）: {e}")
            self._transfer_relations_fallback(from_name, to_name, user_id)

    def _transfer_relations_fallback(self, from_name: str, to_name: str, user_id: str):
        """不依赖 APOC 的关系迁移备选（逐类型处理）"""
        try:
            with self.graph_store.driver.session() as session:
                for rtype in ("CONTAINS", "RELATES_TO", "COMPARES_WITH"):
                    # 出边
                    session.run(
                        f"""
                        MATCH (old:UserTopic {{name: $from_name, user_id: $user_id}})-[r:{rtype}]->(target)
                        WHERE target.name <> $to_name
                        MATCH (new:UserTopic {{name: $to_name, user_id: $user_id}})
                        MERGE (new)-[r2:{rtype}]->(target)
                        SET r2 = properties(r)
                        DELETE r
                        """,
                        from_name=from_name,
                        to_name=to_name,
                        user_id=user_id,
                    )
                    # 入边
                    session.run(
                        f"""
                        MATCH (source)-[r:{rtype}]->(old:UserTopic {{name: $from_name, user_id: $user_id}})
                        WHERE source.name <> $to_name
                        MATCH (new:UserTopic {{name: $to_name, user_id: $user_id}})
                        MERGE (source)-[r2:{rtype}]->(new)
                        SET r2 = properties(r)
                        DELETE r
                        """,
                        from_name=from_name,
                        to_name=to_name,
                        user_id=user_id,
                    )
        except Exception as e:
            print(f"⚠️ 关系迁移备选方案也失败: {e}")

    # ================= 查询 =================

    def search_by_keywords(self, keywords: list[str], user_id: str, status: str = "active", limit: int = 10) -> list[dict]:
        """关键词模糊匹配活跃节点"""
        if not self._available or not keywords:
            return []
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id})
                    WHERE t.status = $status
                      AND ANY(kw IN $keywords WHERE toLower(t.name) CONTAINS toLower(kw))
                    RETURN properties(t) AS props
                    ORDER BY t.weight DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    status=status,
                    keywords=keywords,
                    limit=limit,
                )
                return [dict(r["props"]) for r in result]
        except Exception:
            return []

    def get_top_nodes(self, user_id: str, type: Optional[str] = None, limit: int = 20) -> list[dict]:
        """按 weight 排序取 Top-N 活跃节点，可按 type 过滤"""
        if not self._available:
            return []
        try:
            with self.graph_store.driver.session() as session:
                if type:
                    result = session.run(
                        """
                        MATCH (t:UserTopic {user_id: $user_id, status: 'active', type: $type})
                        RETURN properties(t) AS props
                        ORDER BY t.weight DESC
                        LIMIT $limit
                        """,
                        user_id=user_id,
                        type=type,
                        limit=limit,
                    )
                else:
                    result = session.run(
                        """
                        MATCH (t:UserTopic {user_id: $user_id, status: 'active'})
                        RETURN properties(t) AS props
                        ORDER BY t.weight DESC
                        LIMIT $limit
                        """,
                        user_id=user_id,
                        limit=limit,
                    )
                return [dict(r["props"]) for r in result]
        except Exception:
            return []

    def get_ancestors(self, name: str, user_id: str, ancestor_type: str = "Field") -> list[dict]:
        """沿 CONTAINS 边向上查找指定类型的祖先节点"""
        if not self._available:
            return []
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (ancestor:UserTopic {user_id: $user_id, type: $ancestor_type})
                          -[:CONTAINS*1..3]->
                          (t:UserTopic {name: $name, user_id: $user_id})
                    RETURN properties(ancestor) AS props
                    """,
                    name=name,
                    user_id=user_id,
                    ancestor_type=ancestor_type,
                )
                return [dict(r["props"]) for r in result]
        except Exception:
            return []

    def get_children(self, name: str, user_id: str, limit: int = 20) -> list[dict]:
        """沿 CONTAINS 边向下查找子节点"""
        if not self._available:
            return []
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (parent:UserTopic {name: $name, user_id: $user_id})
                          -[:CONTAINS]->
                          (child:UserTopic {user_id: $user_id})
                    WHERE child.status = 'active'
                    RETURN properties(child) AS props
                    ORDER BY child.weight DESC
                    LIMIT $limit
                    """,
                    name=name,
                    user_id=user_id,
                    limit=limit,
                )
                return [dict(r["props"]) for r in result]
        except Exception:
            return []

    def get_comparisons_among(self, names: list[str], user_id: str) -> list[dict]:
        """获取一组节点之间的 COMPARES_WITH 关系"""
        if not self._available or not names:
            return []
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (a:UserTopic {user_id: $user_id})-[r:COMPARES_WITH]-(b:UserTopic {user_id: $user_id})
                    WHERE a.name IN $names AND b.name IN $names AND a.name < b.name
                    RETURN a.name AS from_name, b.name AS to_name, r.description AS description
                    """,
                    user_id=user_id,
                    names=names,
                )
                return [{"from_name": r["from_name"], "to_name": r["to_name"], "description": r["description"]} for r in result]
        except Exception:
            return []

    def get_full_interest_graph(self, user_id: str, status: str = "active") -> dict:
        """获取完整图谱（nodes + edges），供前端和 API。status: 'active' | 'all'"""
        if not self._available:
            return {"nodes": [], "edges": []}
        try:
            with self.graph_store.driver.session() as session:
                # 节点
                if status == "all":
                    node_result = session.run(
                        """
                        MATCH (t:UserTopic {user_id: $user_id})
                        WHERE t.status IN ['active', 'dormant']
                        RETURN elementId(t) AS eid, properties(t) AS props
                        """,
                        user_id=user_id,
                    )
                else:
                    node_result = session.run(
                        """
                        MATCH (t:UserTopic {user_id: $user_id, status: 'active'})
                        RETURN elementId(t) AS eid, properties(t) AS props
                        """,
                        user_id=user_id,
                    )
                nodes = []
                node_ids = {}  # name → eid mapping
                for r in node_result:
                    props = dict(r["props"])
                    eid = r["eid"]
                    props.pop("user_id", None)
                    props["_eid"] = eid
                    node_ids[props["name"]] = eid
                    nodes.append(props)

                # 边
                if status == "all":
                    edge_result = session.run(
                        """
                        MATCH (a:UserTopic {user_id: $user_id})-[r]->(b:UserTopic {user_id: $user_id})
                        WHERE a.status IN ['active', 'dormant'] AND b.status IN ['active', 'dormant']
                        RETURN a.name AS source, b.name AS target, type(r) AS rel_type, properties(r) AS props
                        """,
                        user_id=user_id,
                    )
                else:
                    edge_result = session.run(
                        """
                        MATCH (a:UserTopic {user_id: $user_id, status: 'active'})
                              -[r]->
                              (b:UserTopic {user_id: $user_id, status: 'active'})
                        RETURN a.name AS source, b.name AS target, type(r) AS rel_type, properties(r) AS props
                        """,
                        user_id=user_id,
                    )
                edges = []
                for r in edge_result:
                    edge_props = dict(r["props"]) if r["props"] else {}
                    edges.append({
                        "source": r["source"],
                        "target": r["target"],
                        "type": r["rel_type"],
                        "description": edge_props.get("description", ""),
                        "weight": edge_props.get("weight", 0.3),
                        "confidence": edge_props.get("confidence", 0.5),
                    })

                return {"nodes": nodes, "edges": edges}
        except Exception as e:
            print(f"⚠️ 获取兴趣图谱失败: {e}")
            return {"nodes": [], "edges": []}

    def get_graph_summary(self, user_id: str) -> list[dict]:
        """
        返回树状方向摘要：Field → Topic → Entity 层级结构。
        只包含活跃节点。
        """
        if not self._available:
            return []
        try:
            with self.graph_store.driver.session() as session:
                # 获取所有 Field 及其子树
                result = session.run(
                    """
                    MATCH (f:UserTopic {user_id: $user_id, type: 'Field', status: 'active'})
                    OPTIONAL MATCH (f)-[:CONTAINS]->(child:UserTopic {user_id: $user_id, status: 'active'})
                    OPTIONAL MATCH (child)-[:CONTAINS]->(grandchild:UserTopic {user_id: $user_id, status: 'active'})
                    RETURN f.name AS field_name, f.description AS field_desc, f.weight AS field_weight,
                           collect(DISTINCT {name: child.name, type: child.type, description: child.description, weight: child.weight}) AS children,
                           collect(DISTINCT {name: grandchild.name, parent: child.name, description: grandchild.description, weight: grandchild.weight}) AS grandchildren
                    ORDER BY f.weight DESC
                    """,
                    user_id=user_id,
                )
                summary = []
                for r in result:
                    field = {
                        "name": r["field_name"],
                        "description": r["field_desc"] or "",
                        "weight": r["field_weight"],
                        "children": [],
                    }
                    # 组装子节点
                    children_map = {}
                    for c in r["children"]:
                        if c["name"]:
                            children_map[c["name"]] = {
                                "name": c["name"],
                                "type": c["type"],
                                "description": c["description"] or "",
                                "weight": c["weight"],
                                "children": [],
                            }
                    # 挂载孙节点
                    for gc in r["grandchildren"]:
                        if gc["name"] and gc["parent"] in children_map:
                            children_map[gc["parent"]]["children"].append({
                                "name": gc["name"],
                                "description": gc["description"] or "",
                                "weight": gc["weight"],
                            })
                    field["children"] = sorted(children_map.values(), key=lambda x: x.get("weight", 0), reverse=True)
                    summary.append(field)
                return summary
        except Exception:
            return []

    # ================= 生命周期管理 =================

    def apply_decay(self, user_id: str) -> dict:
        """
        执行衰减 + dormant 检查。返回 {"decayed": N, "dormant": M}。
        - Topic: 超 60 天未触及 → weight 衰减
        - Entity: 超 90 天未触及 + weight < threshold → dormant
        """
        if not self._available:
            return {"decayed": 0, "dormant": 0}
        now = datetime.now()
        decay_cutoff = (now - timedelta(days=DECAY_START_DAYS)).isoformat()
        dormant_cutoff = (now - timedelta(days=DORMANT_DAYS)).isoformat()
        decayed = 0
        dormant_count = 0
        try:
            with self.graph_store.driver.session() as session:
                # Topic 衰减：简化版（直接乘以衰减因子，不做精确天数计算）
                result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, type: 'Topic', status: 'active'})
                    WHERE t.last_seen < $cutoff
                    SET t.weight = t.weight * 0.9
                    RETURN count(t) AS c
                    """,
                    user_id=user_id,
                    cutoff=decay_cutoff,
                )
                record = result.single()
                decayed = record["c"] if record else 0

                # Entity dormant
                result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, type: 'Entity', status: 'active'})
                    WHERE t.last_seen < $cutoff AND t.weight < $threshold
                    SET t.status = 'dormant'
                    RETURN count(t) AS c
                    """,
                    user_id=user_id,
                    cutoff=dormant_cutoff,
                    threshold=DORMANT_WEIGHT_THRESHOLD,
                )
                record = result.single()
                dormant_count = record["c"] if record else 0
        except Exception as e:
            print(f"⚠️ 衰减执行失败: {e}")
        return {"decayed": decayed, "dormant": dormant_count}

    def dormant_lowest_weight(self, user_id: str, count: int = 10):
        """超容量时把 weight 最低的 N 个活跃节点标记为 dormant（不含 Field）"""
        if not self._available:
            return
        try:
            with self.graph_store.driver.session() as session:
                session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, status: 'active'})
                    WHERE t.type <> 'Field'
                    WITH t ORDER BY t.weight ASC LIMIT $count
                    SET t.status = 'dormant'
                    """,
                    user_id=user_id,
                    count=count,
                )
        except Exception as e:
            print(f"⚠️ 容量治理失败: {e}")

    def merge_nodes(self, keep_name: str, remove_name: str, user_id: str) -> bool:
        """
        合并两个节点：保留 keep，删除 remove。
        属性合并 + 关系迁移 + 记录日志。
        """
        if not self._available:
            return False
        keep = self.find_node(keep_name, user_id)
        remove = self.find_node(remove_name, user_id)
        if not keep or not remove:
            return False

        # 属性合并
        merged_weight = max(keep.get("weight", 0), remove.get("weight", 0))
        merged_hit = (keep.get("hit_count", 0) or 0) + (remove.get("hit_count", 0) or 0)
        keep_desc = keep.get("description", "") or ""
        remove_desc = remove.get("description", "") or ""
        merged_desc = keep_desc if len(keep_desc) >= len(remove_desc) else remove_desc

        self.update_node(keep_name, user_id, weight=merged_weight, hit_count=merged_hit, description=merged_desc)

        # 关系迁移
        self.transfer_relations(remove_name, keep_name, user_id)

        # 物理删除被合并节点
        try:
            with self.graph_store.driver.session() as session:
                session.run(
                    "MATCH (t:UserTopic {name: $name, user_id: $user_id}) DETACH DELETE t",
                    name=remove_name,
                    user_id=user_id,
                )
        except Exception as e:
            print(f"⚠️ 删除被合并节点失败: {e}")
            return False

        self.log_event(user_id, "nodes_merged", {"keep": keep_name, "remove": remove_name}, source="structure_review")
        return True

    def physical_cleanup(self, user_id: str) -> dict:
        """清理超期节点：deleted > 30天，dormant > 180天"""
        if not self._available:
            return {"deleted_cleaned": 0, "dormant_cleaned": 0}
        now = datetime.now()
        delete_cutoff = (now - timedelta(days=SOFT_DELETE_DAYS)).isoformat()
        dormant_cutoff = (now - timedelta(days=PHYSICAL_CLEANUP_DAYS)).isoformat()
        deleted_cleaned = 0
        dormant_cleaned = 0
        try:
            with self.graph_store.driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, status: 'deleted'})
                    WHERE t.deleted_at < $cutoff
                    DETACH DELETE t
                    RETURN count(t) AS c
                    """,
                    user_id=user_id,
                    cutoff=delete_cutoff,
                )
                record = result.single()
                deleted_cleaned = record["c"] if record else 0

                result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, status: 'dormant'})
                    WHERE t.last_seen < $cutoff
                    DETACH DELETE t
                    RETURN count(t) AS c
                    """,
                    user_id=user_id,
                    cutoff=dormant_cutoff,
                )
                record = result.single()
                dormant_cleaned = record["c"] if record else 0
        except Exception as e:
            print(f"⚠️ 物理清理失败: {e}")
        return {"deleted_cleaned": deleted_cleaned, "dormant_cleaned": dormant_cleaned}

    # ================= 健康度指标 =================

    def get_graph_health(self, user_id: str) -> dict:
        """返回图谱质量健康度指标"""
        if not self._available:
            return {"available": False}
        try:
            with self.graph_store.driver.session() as session:
                # 节点统计
                node_stats = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id})
                    RETURN t.status AS status, t.type AS type, count(t) AS c
                    """,
                    user_id=user_id,
                )
                status_counts = {"active": 0, "dormant": 0, "deleted": 0}
                type_counts = {"Field": 0, "Topic": 0, "Entity": 0}
                total_desc_len = 0
                total_nodes = 0
                for r in node_stats:
                    s = r["status"] or "active"
                    t = r["type"] or "Entity"
                    c = r["c"]
                    status_counts[s] = status_counts.get(s, 0) + c
                    if s == "active":
                        type_counts[t] = type_counts.get(t, 0) + c
                    total_nodes += c

                # 关系统计
                rel_result = session.run(
                    """
                    MATCH (a:UserTopic {user_id: $user_id, status: 'active'})
                          -[r]->
                          (b:UserTopic {user_id: $user_id, status: 'active'})
                    RETURN count(r) AS total_rels,
                           sum(CASE WHEN r.confidence < $threshold THEN 1 ELSE 0 END) AS low_conf
                    """,
                    user_id=user_id,
                    threshold=LOW_CONFIDENCE_THRESHOLD,
                )
                rel_record = rel_result.single()
                total_rels = rel_record["total_rels"] if rel_record else 0
                low_conf = rel_record["low_conf"] if rel_record else 0

                # 孤立节点率
                orphan_result = session.run(
                    """
                    MATCH (t:UserTopic {user_id: $user_id, status: 'active'})
                    WHERE NOT (t)-[]-()
                    RETURN count(t) AS orphans
                    """,
                    user_id=user_id,
                )
                orphan_record = orphan_result.single()
                orphans = orphan_record["orphans"] if orphan_record else 0

                active_total = status_counts.get("active", 0)
                orphan_rate = round(orphans / active_total, 3) if active_total > 0 else 0
                avg_connectivity = round(total_rels / active_total, 2) if active_total > 0 else 0

                return {
                    "available": True,
                    "total_active_nodes": active_total,
                    "total_dormant_nodes": status_counts.get("dormant", 0),
                    "total_deleted_nodes": status_counts.get("deleted", 0),
                    "total_relations": total_rels,
                    "field_count": type_counts.get("Field", 0),
                    "topic_count": type_counts.get("Topic", 0),
                    "entity_count": type_counts.get("Entity", 0),
                    "orphan_rate": orphan_rate,
                    "avg_connectivity": avg_connectivity,
                    "low_confidence_relations": low_conf,
                }
        except Exception as e:
            print(f"⚠️ 健康度指标查询失败: {e}")
            return {"available": False, "error": str(e)}

    # ================= 日志 =================

    def _init_log_table(self):
        """初始化 interest_graph_log 表"""
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interest_graph_log (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    source TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ig_log_user "
                "ON interest_graph_log(user_id, created_at DESC)"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ interest_graph_log 表初始化失败: {e}")

    def log_event(self, user_id: str, event_type: str, detail: dict, source: str = "qa_distill"):
        """记录图谱变更事件"""
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO interest_graph_log (id, user_id, event_type, detail, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    user_id,
                    event_type,
                    json.dumps(detail, ensure_ascii=False),
                    source,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_recent_logs(self, user_id: str, limit: int = 20) -> list[dict]:
        """获取最近 N 条生长日志"""
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM interest_graph_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            conn.close()
            return [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "detail": json.loads(row["detail"]) if row["detail"] else {},
                    "source": row["source"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        except Exception:
            return []

    # ================= 辅助 =================

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
