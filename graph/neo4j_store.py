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
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def init_schema(self):
        """创建约束和索引"""
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

    def clear_all(self):
        """清空图数据库（谨慎使用）"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
