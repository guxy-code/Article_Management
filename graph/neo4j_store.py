"""
Neo4j 图数据库操作模块（多用户版）
所有节点均带 user_id 属性，实现完全数据隔离。
"""

import os
from typing import Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class GraphStore:
    """Neo4j 图数据库封装（支持多用户隔离）"""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "12345678")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            self.available = True
        except Exception as e:
            print(f"⚠️ Neo4j 不可用，知识图谱功能已禁用: {e}")
            self.driver = None
            self.available = False

    def _unavailable_response(self) -> dict:
        return {"nodes": [], "edges": [], "neo4j_unavailable": True}

    def close(self):
        if self.driver:
            self.driver.close()

    def init_schema(self):
        """创建约束和索引（多用户版：以 name+user_id 联合唯一）"""
        if not self.available:
            return
        with self.driver.session() as session:
            # 删除所有旧的单字段唯一约束（通过 SHOW CONSTRAINTS 查找，不依赖约束名）
            result = session.run("SHOW CONSTRAINTS")
            for r in result:
                props = r["properties"]
                labels = r.get("labelsOrTypes", [])
                # 只删除单字段（不含 user_id）的唯一约束
                if len(props) == 1 and "user_id" not in props:
                    name = r["name"]
                    try:
                        session.run(f"DROP CONSTRAINT {name}")
                    except Exception:
                        pass

            # 创建新的复合唯一约束
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE (p.title, p.user_id) IS NODE KEY",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Method) REQUIRE (m.name, m.user_id) IS NODE KEY",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Problem) REQUIRE (pr.name, pr.user_id) IS NODE KEY",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Dataset) REQUIRE (d.name, d.user_id) IS NODE KEY",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE (c.name, c.user_id) IS NODE KEY",
            ]
            for cypher in constraints:
                try:
                    session.run(cypher)
                except Exception:
                    pass  # 旧版 Neo4j 不支持 IS NODE KEY，降级处理

    # --- 写入 ---

    def add_paper_graph(self, paper_data: dict, user_id: str = "system"):
        """
        将 LLM 提取的结构化数据写入 Neo4j（带 user_id 隔离）。
        """
        if not self.available:
            return
        with self.driver.session() as session:
            title = paper_data.get("title", "")
            authors = paper_data.get("authors", "")

            # Paper 节点
            session.run(
                "MERGE (p:Paper {title: $title, user_id: $user_id}) SET p.authors = $authors",
                title=title, authors=authors, user_id=user_id,
            )

            # Method 节点 + PROPOSES 关系
            for method in paper_data.get("methods", []):
                session.run(
                    """
                    MERGE (m:Method {name: $name, user_id: $user_id})
                    SET m.description = $desc
                    WITH m
                    MATCH (p:Paper {title: $title, user_id: $user_id})
                    MERGE (p)-[:PROPOSES]->(m)
                    """,
                    name=method["name"], desc=method.get("description", ""),
                    title=title, user_id=user_id,
                )

            # Problem 节点 + ADDRESSES 关系
            for problem in paper_data.get("problems", []):
                session.run(
                    """
                    MERGE (pr:Problem {name: $name, user_id: $user_id})
                    SET pr.description = $desc
                    WITH pr
                    MATCH (p:Paper {title: $title, user_id: $user_id})
                    MERGE (p)-[:ADDRESSES]->(pr)
                    """,
                    name=problem["name"], desc=problem.get("description", ""),
                    title=title, user_id=user_id,
                )

            # Dataset 节点 + EVALUATES_ON 关系
            for dataset in paper_data.get("datasets", []):
                session.run(
                    """
                    MERGE (d:Dataset {name: $name, user_id: $user_id})
                    WITH d
                    MATCH (p:Paper {title: $title, user_id: $user_id})
                    MERGE (p)-[:EVALUATES_ON]->(d)
                    """,
                    name=dataset, title=title, user_id=user_id,
                )

            # Concept 节点 + USES_CONCEPT 关系
            for concept in paper_data.get("concepts", []):
                session.run(
                    """
                    MERGE (c:Concept {name: $name, user_id: $user_id})
                    WITH c
                    MATCH (p:Paper {title: $title, user_id: $user_id})
                    MERGE (p)-[:USES_CONCEPT]->(c)
                    """,
                    name=concept, title=title, user_id=user_id,
                )

            # 额外关系（IMPROVES, SOLVES, USES）
            for rel in paper_data.get("relations", []):
                rel_type = rel.get("type", "RELATED_TO")
                from_name = rel.get("from", "")
                to_name = rel.get("to", "")
                if not from_name or not to_name:
                    continue

                if rel_type == "IMPROVES":
                    session.run(
                        """
                        MERGE (a:Method {name: $from_name, user_id: $user_id})
                        MERGE (b:Method {name: $to_name, user_id: $user_id})
                        MERGE (a)-[:IMPROVES]->(b)
                        """,
                        from_name=from_name, to_name=to_name, user_id=user_id,
                    )
                elif rel_type == "SOLVES":
                    session.run(
                        """
                        MERGE (m:Method {name: $from_name, user_id: $user_id})
                        MERGE (pr:Problem {name: $to_name, user_id: $user_id})
                        MERGE (m)-[:SOLVES]->(pr)
                        """,
                        from_name=from_name, to_name=to_name, user_id=user_id,
                    )
                elif rel_type == "USES":
                    session.run(
                        """
                        MERGE (m:Method {name: $from_name, user_id: $user_id})
                        MERGE (c:Concept {name: $to_name, user_id: $user_id})
                        MERGE (m)-[:USES]->(c)
                        """,
                        from_name=from_name, to_name=to_name, user_id=user_id,
                    )

    # --- 查询 ---

    def get_full_graph(self, user_id: str = "system") -> dict:
        """获取当前用户的完整图谱（排除 UserTopic，那属于兴趣图谱）"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n {user_id: $user_id})
                WHERE NOT n:UserTopic
                RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props
                """,
                user_id=user_id,
            )
            for record in result:
                props = dict(record["props"])
                props.pop("user_id", None)  # 不暴露给前端
                nodes.append({
                    "id": str(record["id"]),
                    "type": record["labels"][0] if record["labels"] else "Unknown",
                    "label": props.get("title") or props.get("name") or "Unknown",
                    "properties": props,
                })

            result = session.run(
                """
                MATCH (a {user_id: $user_id})-[r]->(b {user_id: $user_id})
                WHERE NOT a:UserTopic AND NOT b:UserTopic
                RETURN id(a) AS source, id(b) AS target, type(r) AS rel_type
                """,
                user_id=user_id,
            )
            for record in result:
                edges.append({
                    "source": str(record["source"]),
                    "target": str(record["target"]),
                    "type": record["rel_type"],
                })

        return {"nodes": nodes, "edges": edges}

    def get_paper_subgraph(self, title: str, user_id: str = "system") -> dict:
        """获取某篇论文的知识骨架（2跳，排除其他 Paper 节点）"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (p:Paper {title: $title, user_id: $user_id})-[*1..2]-(n)
                WHERE ALL(node IN nodes(path)
                    WHERE node = p
                       OR (NOT 'Paper' IN labels(node) AND node.user_id = $user_id))
                UNWIND nodes(path) AS node
                UNWIND relationships(path) AS rel
                WITH DISTINCT node, rel
                RETURN
                    id(node) AS nid, labels(node) AS nlabels, properties(node) AS nprops,
                    id(startNode(rel)) AS src, id(endNode(rel)) AS tgt, type(rel) AS rel_type
                """,
                title=title, user_id=user_id,
            )

            seen_nodes, seen_edges = set(), set()
            for record in self._iter_graph_records(result, seen_nodes, seen_edges):
                if record["node"]:
                    nodes.append(record["node"])
                if record["edge"]:
                    edges.append(record["edge"])

        return {"nodes": nodes, "edges": edges}

    def get_stats(self, user_id: str = "system") -> dict:
        """获取当前用户的图谱统计信息（排除 UserTopic）"""
        if not self.available:
            return {"nodes": {}, "total_edges": 0, "neo4j_unavailable": True}
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n {user_id: $user_id})
                WHERE NOT n:UserTopic
                RETURN labels(n)[0] AS label, count(n) AS count
                """,
                user_id=user_id,
            )
            node_counts = {r["label"]: r["count"] for r in result}

            result = session.run(
                """
                MATCH (a {user_id: $user_id})-[r]->(b {user_id: $user_id})
                WHERE NOT a:UserTopic AND NOT b:UserTopic
                RETURN count(r) AS count
                """,
                user_id=user_id,
            )
            edge_count = result.single()["count"]

        return {"nodes": node_counts, "total_edges": edge_count}

    def get_papers_subgraph(self, titles: list[str], user_id: str = "system") -> dict:
        """获取多篇论文的合并子图"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (p:Paper {user_id: $user_id})-[*1..2]-(n)
                WHERE p.title IN $titles
                  AND ALL(node IN nodes(path)
                      WHERE node = p
                         OR (NOT 'Paper' IN labels(node) AND node.user_id = $user_id)
                         OR (node.user_id = $user_id AND node.title IN $titles))
                UNWIND nodes(path) AS node
                UNWIND relationships(path) AS rel
                WITH DISTINCT node, rel
                RETURN
                    id(node) AS nid, labels(node) AS nlabels, properties(node) AS nprops,
                    id(startNode(rel)) AS src, id(endNode(rel)) AS tgt, type(rel) AS rel_type
                """,
                titles=titles, user_id=user_id,
            )

            seen_nodes, seen_edges = set(), set()
            for record in self._iter_graph_records(result, seen_nodes, seen_edges):
                if record["node"]:
                    nodes.append(record["node"])
                if record["edge"]:
                    edges.append(record["edge"])

        return {"nodes": nodes, "edges": edges}

    def get_keyword_graph(self, user_id: str = "system") -> dict:
        """获取当前用户的关键词关联图（Paper + Concept 二部图）"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Paper {user_id: $user_id})-[r:USES_CONCEPT]->(c:Concept {user_id: $user_id})
                RETURN
                    id(p) AS pid, properties(p) AS pprops,
                    id(c) AS cid, properties(c) AS cprops,
                    type(r) AS rel_type
                """,
                user_id=user_id,
            )

            seen_nodes = set()
            for record in result:
                pid, cid = str(record["pid"]), str(record["cid"])
                if pid not in seen_nodes:
                    seen_nodes.add(pid)
                    pprops = dict(record["pprops"])
                    pprops.pop("user_id", None)
                    nodes.append({"id": pid, "type": "Paper", "label": pprops.get("title", ""), "properties": pprops})
                if cid not in seen_nodes:
                    seen_nodes.add(cid)
                    cprops = dict(record["cprops"])
                    cprops.pop("user_id", None)
                    nodes.append({"id": cid, "type": "Keyword", "label": cprops.get("name", ""), "properties": cprops})
                edges.append({"source": pid, "target": cid, "type": record["rel_type"]})

        return {"nodes": nodes, "edges": edges}

    def get_all_concepts(self, user_id: str = "system") -> list[str]:
        """获取当前用户的所有 Concept 节点名称"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Concept {user_id: $user_id}) RETURN c.name AS name ORDER BY name",
                user_id=user_id,
            )
            return [r["name"] for r in result]

    def get_concept_frequency(self, user_id: str = "system") -> list[dict]:
        """返回当前用户每个概念被几篇论文引用，按频率降序"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept {user_id: $user_id})<-[:USES_CONCEPT]-(p:Paper {user_id: $user_id})
                RETURN c.name AS name, count(p) AS count
                ORDER BY count DESC, name
                """,
                user_id=user_id,
            )
            return [{"name": r["name"], "count": r["count"]} for r in result]

    def get_method_evolution(self, user_id: str = "system") -> list[dict]:
        """获取当前用户的方法改进关系"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Method {user_id: $user_id})-[:IMPROVES]->(b:Method {user_id: $user_id})
                RETURN a.name AS from_method, b.name AS to_method
                """,
                user_id=user_id,
            )
            return [{"from": r["from_method"], "to": r["to_method"]} for r in result]

    def get_problems_solutions(self, user_id: str = "system") -> list[dict]:
        """获取当前用户论文解决的问题列表"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Paper {user_id: $user_id})-[:ADDRESSES]->(pr:Problem {user_id: $user_id})
                RETURN p.title AS paper, pr.name AS problem
                ORDER BY p.title
                """,
                user_id=user_id,
            )
            return [{"paper": r["paper"], "problem": r["problem"]} for r in result]

    def query_related(self, entity: str, user_id: str = "system") -> list[dict]:
        """查询当前用户图谱中与某个实体相关的所有关系"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a {user_id: $user_id})-[r]-(b {user_id: $user_id})
                WHERE a.name = $entity OR a.title = $entity
                   OR toLower(a.name) CONTAINS toLower($entity)
                   OR toLower(a.title) CONTAINS toLower($entity)
                RETURN
                    coalesce(a.title, a.name) AS source,
                    labels(a)[0] AS source_type,
                    type(r) AS relation,
                    coalesce(b.title, b.name) AS target,
                    labels(b)[0] AS target_type,
                    startNode(r) = a AS is_outgoing
                LIMIT 20
                """,
                entity=entity, user_id=user_id,
            )
            triples = []
            for r in result:
                if r["is_outgoing"]:
                    triples.append({"subject": r["source"], "subject_type": r["source_type"],
                                    "relation": r["relation"], "object": r["target"], "object_type": r["target_type"]})
                else:
                    triples.append({"subject": r["target"], "subject_type": r["target_type"],
                                    "relation": r["relation"], "object": r["source"], "object_type": r["source_type"]})
            return triples

    def query_path(self, entity_a: str, entity_b: str, user_id: str = "system") -> list[dict]:
        """查询当前用户图谱中两个实体之间的最短路径"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a {user_id: $user_id}), (b {user_id: $user_id})
                WHERE (a.name = $a OR a.title = $a OR toLower(a.name) CONTAINS toLower($a))
                  AND (b.name = $b OR b.title = $b OR toLower(b.name) CONTAINS toLower($b))
                WITH a, b LIMIT 1
                MATCH path = shortestPath((a)-[*..5]-(b))
                UNWIND relationships(path) AS r
                RETURN
                    coalesce(startNode(r).title, startNode(r).name) AS source,
                    type(r) AS relation,
                    coalesce(endNode(r).title, endNode(r).name) AS target
                """,
                a=entity_a, b=entity_b, user_id=user_id,
            )
            return [{"source": r["source"], "relation": r["relation"], "target": r["target"]} for r in result]

    def get_paper_concepts(self, title: str, user_id: str = "system") -> list[str]:
        """获取某篇论文关联的 Concept 列表"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:Paper {title: $title, user_id: $user_id})-[:USES_CONCEPT]->(c:Concept {user_id: $user_id}) RETURN c.name AS name",
                title=title, user_id=user_id,
            )
            return [r["name"] for r in result]

    def get_papers_with_concepts(self, user_id: str = "system") -> list[dict]:
        """获取当前用户所有论文及其关联的概念"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Paper {user_id: $user_id})
                OPTIONAL MATCH (p)-[:USES_CONCEPT]->(c:Concept {user_id: $user_id})
                RETURN p.title AS title, p.authors AS authors, collect(c.name) AS concepts
                ORDER BY p.title
                """,
                user_id=user_id,
            )
            return [{"title": r["title"], "authors": r["authors"] or "", "concepts": r["concepts"]} for r in result]

    # --- 知识树掌握状态（自生长记忆） ---

    def update_node_mastery(self, topics: list[str], user_id: str = "system") -> int:
        """
        根据蒸馏出的 topics 更新对应节点的掌握状态（问答后异步调用）。
        对每个 topic 做模糊匹配（toLower CONTAINS），命中的节点：
        - query_count += 1、last_queried = now
        - 状态迁移：query_count >= 3 → mastered，否则 learning
        用 Cypher CASE 原子完成，避免先查后写的竞态。
        返回受影响的节点总数。

        注意：topics（蒸馏产出，可能含中文）与 Neo4j 节点名（图谱提取产出，多英文）
        是两套独立 LLM 结果，模糊匹配无法保证全覆盖，这是知识树准确度的天然上限。
        """
        if not self.available or not topics:
            return 0
        from datetime import datetime
        now = datetime.now().isoformat()
        affected = 0
        with self.driver.session() as session:
            for topic in topics:
                t = (topic or "").strip()
                if not t:
                    continue
                result = session.run(
                    """
                    MATCH (n {user_id: $user_id})
                    WHERE (n:Method OR n:Problem OR n:Concept OR n:Dataset)
                      AND (toLower(n.name) CONTAINS toLower($topic)
                           OR toLower($topic) CONTAINS toLower(n.name))
                    SET n.query_count = coalesce(n.query_count, 0) + 1,
                        n.last_queried = $now,
                        n.mastery = CASE
                            WHEN coalesce(n.query_count, 0) + 1 >= 3 THEN 'mastered'
                            ELSE 'learning'
                        END
                    RETURN count(n) AS c
                    """,
                    topic=t, user_id=user_id, now=now,
                )
                record = result.single()
                if record:
                    affected += record["c"]
        return affected

    def get_knowledge_tree(self, user_id: str = "system") -> list[dict]:
        """
        返回当前用户所有非 Paper 节点的掌握状态概览。
        未被问及过的节点没有 mastery 属性，用 coalesce 兜底为 'unexplored'。
        """
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n {user_id: $user_id})
                WHERE NOT n:Paper
                RETURN n.name AS name,
                       labels(n)[0] AS type,
                       coalesce(n.mastery, 'unexplored') AS mastery,
                       coalesce(n.query_count, 0) AS query_count,
                       n.last_queried AS last_queried
                ORDER BY query_count DESC, name
                """,
                user_id=user_id,
            )
            return [
                {
                    "name": r["name"],
                    "type": r["type"],
                    "mastery": r["mastery"],
                    "query_count": r["query_count"],
                    "last_queried": r["last_queried"],
                }
                for r in result
            ]

    def clear_all(self, user_id: Optional[str] = None):
        """清空图数据库，如果指定 user_id 只清空该用户的数据"""
        if not self.available:
            return
        with self.driver.session() as session:
            if user_id:
                session.run("MATCH (n {user_id: $user_id}) DETACH DELETE n", user_id=user_id)
            else:
                session.run("MATCH (n) DETACH DELETE n")

    def delete_paper_graph(self, title: str, user_id: str = "system"):
        """删除某篇论文在图谱中的节点和关系，并清理孤立子节点"""
        if not self.available:
            return
        with self.driver.session() as session:
            # 1. 删除 Paper 节点及其所有直接关系（PROPOSES, ADDRESSES, EVALUATES_ON, USES_CONCEPT）
            session.run(
                "MATCH (p:Paper {title: $title, user_id: $user_id}) DETACH DELETE p",
                title=title, user_id=user_id,
            )
            # 2. 删除不再被任何 Paper 引用的孤立子节点（Method/Problem/Concept/Dataset）
            #    DETACH 确保同时删除子节点间残留的 IMPROVES/SOLVES/USES 关系
            session.run(
                """
                MATCH (n {user_id: $user_id})
                WHERE NOT n:Paper
                  AND NOT EXISTS {
                    MATCH (p:Paper {user_id: $user_id})-[]->(n)
                  }
                DETACH DELETE n
                """,
                user_id=user_id,
            )

    # --- 辅助方法 ---

    def _iter_graph_records(self, result, seen_nodes: set, seen_edges: set):
        """迭代图谱查询结果，去重节点和边，过滤 user_id 属性"""
        for record in result:
            nid = str(record["nid"])
            node_entry = None
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nprops = dict(record["nprops"])
                nprops.pop("user_id", None)
                node_entry = {
                    "id": nid,
                    "type": record["nlabels"][0] if record["nlabels"] else "Unknown",
                    "label": nprops.get("title") or nprops.get("name") or "",
                    "properties": nprops,
                }

            edge_key = f"{record['src']}-{record['rel_type']}-{record['tgt']}"
            edge_entry = None
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edge_entry = {
                    "source": str(record["src"]),
                    "target": str(record["tgt"]),
                    "type": record["rel_type"],
                }

            if node_entry or edge_entry:
                yield {"node": node_entry, "edge": edge_entry}
