"""
Neo4j 连通性测试
用法：python graph/test_connection.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_neo4j():
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "12345678")

    print("=" * 50)
    print("🔗 Neo4j 连通性测试")
    print("=" * 50)
    print(f"  URI: {uri}")
    print(f"  User: {user}")
    print()

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))

        # 验证连接
        driver.verify_connectivity()
        print("  ✅ 连接成功！")

        # 获取数据库信息
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            print(f"  ✅ 查询测试: RETURN 1 = {record['num']}")

            # 获取节点数量
            result = session.run("MATCH (n) RETURN count(n) AS count")
            record = result.single()
            print(f"  📊 当前节点数: {record['count']}")

            # 获取关系数量
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            record = result.single()
            print(f"  📊 当前关系数: {record['count']}")

        driver.close()
        print()
        print("  🎉 Neo4j 准备就绪！")
        return True

    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        print()
        print("  排查步骤：")
        print("  1. 确认 Neo4j Desktop 中数据库已启动（状态为 Running）")
        print("  2. 确认密码正确")
        print("  3. 确认端口 7687 没有被占用")
        return False


if __name__ == "__main__":
    print()
    success = test_neo4j()
    print()
    if not success:
        sys.exit(1)
