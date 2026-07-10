"""
Neo4j 图数据库操作模块
负责节点和关系的增删查。
"""

import os
from typing import Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class GraphStore:
    """Neo4j 图数据库封装"""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "12345678")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # 主动探测连接是否可用
            self.driver.verify_connectivity()
            self.available = True
        except Exception as e:
            print(f"⚠️ Neo4j 不可用，知识图谱功能已禁用: {e}")
            self.driver = None
            self.available = False

    def _unavailable_response(self) -> dict:
        """当 Neo4j 不可用时返回的统一空响应"""
        return {"nodes": [], "edges": [], "neo4j_unavailable": True}

    def close(self):
        if self.driver:
            self.driver.close()

    def init_schema(self):
        """创建约束和索引"""
        if not self.available:
            return
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.title IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Method) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Problem) REQUIRE pr.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Dataset) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for cypher in constraints:
                session.run(cypher)

    # --- 写入 ---

    def add_paper_graph(self, paper_data: dict):
        """
        将 LLM 提取的结构化数据写入 Neo4j。

        paper_data 结构：
        {
            "title": "论文标题",
            "authors": "作者",
            "methods": [{"name": "...", "description": "..."}],
            "problems": [{"name": "...", "description": "..."}],
            "concepts": ["concept1", "concept2"],
            "datasets": ["dataset1", "dataset2"],
            "relations": [
                {"type": "IMPROVES", "from": "方法A", "to": "方法B"},
                {"type": "SOLVES", "from": "方法A", "to": "问题X"},
                ...
            ]
        }
        """
        if not self.available:
            return
        with self.driver.session() as session:
            title = paper_data.get("title", "")
            authors = paper_data.get("authors", "")

            # 创建 Paper 节点
            session.run(
                "MERGE (p:Paper {title: $title}) SET p.authors = $authors",
                title=title, authors=authors,
            )

            # 创建 Method 节点 + PROPOSES 关系
            for method in paper_data.get("methods", []):
                session.run(
                    """
                    MERGE (m:Method {name: $name})
                    SET m.description = $desc
                    WITH m
                    MATCH (p:Paper {title: $title})
                    MERGE (p)-[:PROPOSES]->(m)
                    """,
                    name=method["name"],
                    desc=method.get("description", ""),
                    title=title,
                )

            # 创建 Problem 节点 + Paper ADDRESSES 关系
            for problem in paper_data.get("problems", []):
                session.run(
                    """
                    MERGE (pr:Problem {name: $name})
                    SET pr.description = $desc
                    WITH pr
                    MATCH (p:Paper {title: $title})
                    MERGE (p)-[:ADDRESSES]->(pr)
                    """,
                    name=problem["name"],
                    desc=problem.get("description", ""),
                    title=title,
                )

            # 创建 Dataset 节点 + EVALUATES_ON 关系
            for dataset in paper_data.get("datasets", []):
                session.run(
                    """
                    MERGE (d:Dataset {name: $name})
                    WITH d
                    MATCH (p:Paper {title: $title})
                    MERGE (p)-[:EVALUATES_ON]->(d)
                    """,
                    name=dataset, title=title,
                )

            # 创建 Concept 节点 + USES 关系
            for concept in paper_data.get("concepts", []):
                session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    WITH c
                    MATCH (p:Paper {title: $title})
                    MERGE (p)-[:USES_CONCEPT]->(c)
                    """,
                    name=concept, title=title,
                )

            # 创建额外关系（IMPROVES, SOLVES 等）
            for rel in paper_data.get("relations", []):
                rel_type = rel.get("type", "RELATED_TO")
                from_name = rel.get("from", "")
                to_name = rel.get("to", "")

                if not from_name or not to_name:
                    continue

                # 动态关系：Method→Method 或 Method→Problem
                if rel_type == "IMPROVES":
                    session.run(
                        """
                        MERGE (a:Method {name: $from_name})
                        MERGE (b:Method {name: $to_name})
                        MERGE (a)-[:IMPROVES]->(b)
                        """,
                        from_name=from_name, to_name=to_name,
                    )
                elif rel_type == "SOLVES":
                    session.run(
                        """
                        MERGE (m:Method {name: $from_name})
                        MERGE (pr:Problem {name: $to_name})
                        MERGE (m)-[:SOLVES]->(pr)
                        """,
                        from_name=from_name, to_name=to_name,
                    )
                elif rel_type == "USES":
                    session.run(
                        """
                        MERGE (m:Method {name: $from_name})
                        MERGE (c:Concept {name: $to_name})
                        MERGE (m)-[:USES]->(c)
                        """,
                        from_name=from_name, to_name=to_name,
                    )

    # --- 查询 ---

    def get_full_graph(self) -> dict:
        """获取完整图谱（所有节点和边），用于前端可视化"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            # 获取所有节点
            result = session.run(
                """
                MATCH (n)
                RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props
                """
            )
            for record in result:
                node_labels = record["labels"]
                props = record["props"]
                nodes.append({
                    "id": str(record["id"]),
                    "type": node_labels[0] if node_labels else "Unknown",
                    "label": props.get("title") or props.get("name") or "Unknown",
                    "properties": dict(props),
                })

            # 获取所有关系
            result = session.run(
                """
                MATCH (a)-[r]->(b)
                RETURN id(a) AS source, id(b) AS target, type(r) AS rel_type
                """
            )
            for record in result:
                edges.append({
                    "source": str(record["source"]),
                    "target": str(record["target"]),
                    "type": record["rel_type"],
                })

        return {"nodes": nodes, "edges": edges}

    def get_paper_subgraph(self, title: str) -> dict:
        """获取某篇论文的知识骨架（2跳，排除其他 Paper 节点）"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            # 2跳查询，但路径中间节点不能是 Paper（排除其他论文）
            result = session.run(
                """
                MATCH path = (p:Paper {title: $title})-[*1..2]-(n)
                WHERE ALL(node IN nodes(path) WHERE node = p OR NOT 'Paper' IN labels(node))
                UNWIND nodes(path) AS node
                UNWIND relationships(path) AS rel
                WITH DISTINCT node, rel
                RETURN
                    id(node) AS nid,
                    labels(node) AS nlabels,
                    properties(node) AS nprops,
                    id(startNode(rel)) AS src,
                    id(endNode(rel)) AS tgt,
                    type(rel) AS rel_type
                """,
                title=title,
            )

            seen_nodes = set()
            seen_edges = set()

            for record in result:
                nid = str(record["nid"])
                if nid not in seen_nodes:
                    seen_nodes.add(nid)
                    nprops = record["nprops"]
                    nodes.append({
                        "id": nid,
                        "type": record["nlabels"][0] if record["nlabels"] else "Unknown",
                        "label": nprops.get("title") or nprops.get("name") or "",
                        "properties": dict(nprops),
                    })

                edge_key = f"{record['src']}-{record['rel_type']}-{record['tgt']}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": str(record["src"]),
                        "target": str(record["tgt"]),
                        "type": record["rel_type"],
                    })

        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> dict:
        """获取图谱统计信息"""
        if not self.available:
            return {"nodes": {}, "total_edges": 0, "neo4j_unavailable": True}
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                RETURN labels(n)[0] AS label, count(n) AS count
                """
            )
            node_counts = {r["label"]: r["count"] for r in result}

            result = session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            edge_count = result.single()["count"]

        return {"nodes": node_counts, "total_edges": edge_count}

    def get_papers_subgraph(self, titles: list[str]) -> dict:
        """获取多篇论文的合并子图（2跳，排除列表外的其他 Paper 节点）"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (p:Paper)-[*1..2]-(n)
                WHERE p.title IN $titles
                  AND ALL(node IN nodes(path) WHERE node = p OR NOT 'Paper' IN labels(node) OR node.title IN $titles)
                UNWIND nodes(path) AS node
                UNWIND relationships(path) AS rel
                WITH DISTINCT node, rel
                RETURN
                    id(node) AS nid,
                    labels(node) AS nlabels,
                    properties(node) AS nprops,
                    id(startNode(rel)) AS src,
                    id(endNode(rel)) AS tgt,
                    type(rel) AS rel_type
                """,
                titles=titles,
            )

            seen_nodes = set()
            seen_edges = set()

            for record in result:
                nid = str(record["nid"])
                if nid not in seen_nodes:
                    seen_nodes.add(nid)
                    nprops = record["nprops"]
                    nodes.append({
                        "id": nid,
                        "type": record["nlabels"][0] if record["nlabels"] else "Unknown",
                        "label": nprops.get("title") or nprops.get("name") or "",
                        "properties": dict(nprops),
                    })

                edge_key = f"{record['src']}-{record['rel_type']}-{record['tgt']}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": str(record["src"]),
                        "target": str(record["tgt"]),
                        "type": record["rel_type"],
                    })

        return {"nodes": nodes, "edges": edges}

    def get_keyword_graph(self) -> dict:
        """获取关键词关联图：Paper + Concept 的二部图，展示论文之间通过共享概念的关联"""
        if not self.available:
            return self._unavailable_response()
        nodes = []
        edges = []

        with self.driver.session() as session:
            # 只取 Paper 和 Concept 节点，以及它们之间的 USES_CONCEPT 关系
            result = session.run(
                """
                MATCH (p:Paper)-[r:USES_CONCEPT]->(c:Concept)
                RETURN
                    id(p) AS pid, properties(p) AS pprops,
                    id(c) AS cid, properties(c) AS cprops,
                    type(r) AS rel_type
                """
            )

            seen_nodes = set()

            for record in result:
                pid = str(record["pid"])
                cid = str(record["cid"])

                if pid not in seen_nodes:
                    seen_nodes.add(pid)
                    pprops = record["pprops"]
                    nodes.append({
                        "id": pid,
                        "type": "Paper",
                        "label": pprops.get("title", ""),
                        "properties": dict(pprops),
                    })

                if cid not in seen_nodes:
                    seen_nodes.add(cid)
                    cprops = record["cprops"]
                    nodes.append({
                        "id": cid,
                        "type": "Keyword",
                        "label": cprops.get("name", ""),
                        "properties": dict(cprops),
                    })

                edges.append({
                    "source": pid,
                    "target": cid,
                    "type": record["rel_type"],
                })

        return {"nodes": nodes, "edges": edges}

    def get_all_concepts(self) -> list[str]:
        """获取所有 Concept 节点名称"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run("MATCH (c:Concept) RETURN c.name AS name ORDER BY name")
            return [r["name"] for r in result]

    def get_concept_frequency(self) -> list[dict]:
        """返回每个概念被几篇论文引用，按频率降序"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept)<-[:USES_CONCEPT]-(p:Paper)
                RETURN c.name AS name, count(p) AS count
                ORDER BY count DESC, name
                """
            )
            return [{"name": r["name"], "count": r["count"]} for r in result]

    def get_method_evolution(self) -> list[dict]:
        """获取所有方法改进关系"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a:Method)-[:IMPROVES]->(b:Method)
                RETURN a.name AS from_method, b.name AS to_method
                """
            )
            return [{"from": r["from_method"], "to": r["to_method"]} for r in result]

    def get_problems_solutions(self) -> list[dict]:
        """获取论文解决的问题列表"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Paper)-[:ADDRESSES]->(pr:Problem)
                RETURN p.title AS paper, pr.name AS problem
                ORDER BY p.title
                """
            )
            return [{"paper": r["paper"], "problem": r["problem"]} for r in result]

    def query_related(self, entity: str) -> list[dict]:
        """查询与某个实体相关的所有关系。"""
        if not self.available:
            return []
        with self.driver.session() as session:
            # 先精确匹配，再模糊匹配
            result = session.run(
                """
                MATCH (a)-[r]-(b)
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
                entity=entity,
            )

            triples = []
            for r in result:
                if r["is_outgoing"]:
                    triples.append({
                        "subject": r["source"],
                        "subject_type": r["source_type"],
                        "relation": r["relation"],
                        "object": r["target"],
                        "object_type": r["target_type"],
                    })
                else:
                    triples.append({
                        "subject": r["target"],
                        "subject_type": r["target_type"],
                        "relation": r["relation"],
                        "object": r["source"],
                        "object_type": r["source_type"],
                    })
            return triples

    def query_path(self, entity_a: str, entity_b: str) -> list[dict]:
        """查询两个实体之间的最短路径"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (a), (b)
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
                a=entity_a, b=entity_b,
            )
            return [{"source": r["source"], "relation": r["relation"], "target": r["target"]} for r in result]

    def get_paper_concepts(self, title: str) -> list[str]:
        """获取某篇论文关联的 Concept 列表"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:Paper {title: $title})-[:USES_CONCEPT]->(c:Concept) RETURN c.name AS name",
                title=title,
            )
            return [r["name"] for r in result]

    def get_papers_with_concepts(self) -> list[dict]:
        """获取所有论文及其关联的概念"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Paper)
                OPTIONAL MATCH (p)-[:USES_CONCEPT]->(c:Concept)
                RETURN p.title AS title, p.authors AS authors, collect(c.name) AS concepts
                ORDER BY p.title
                """
            )
            return [
                {"title": r["title"], "authors": r["authors"] or "", "concepts": r["concepts"]}
                for r in result
            ]

    def clear_all(self):
        """清空图数据库（谨慎使用）"""
        if not self.available:
            return
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
