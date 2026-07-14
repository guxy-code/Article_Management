"""
残留数据诊断 & 清理脚本
------------------------------------------------
背景：论文数据分散在 4 个独立存储中，删除论文时如果某个存储清理失败
（例如 Neo4j 当时不可用），就会出现 Library 已空但首页/统计页仍显示论文数的不一致。

本脚本会：
  1) 诊断各存储当前的数据量（--diagnose，默认行为）
  2) 按需清理残留数据（--clean）

用法：
  python cleanup_residual.py                # 只诊断，不改动任何数据
  python cleanup_residual.py --clean         # 清空所有存储中的残留论文数据
  python cleanup_residual.py --clean --user <user_id>   # 只清理指定用户
"""

import os
import sys
import sqlite3
import argparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH") or os.path.join(BASE_DIR, "sessions.db")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_papers")


# ---------------- 诊断 ----------------

def diagnose(user_id: str | None):
    print("=" * 60)
    print("残留数据诊断" + (f"（用户: {user_id}）" if user_id else "（所有用户）"))
    print("=" * 60)

    # 1. Chroma 向量库
    try:
        from store.vector_store import VectorStore
        vs = VectorStore()
        titles = vs.list_papers(user_id=user_id)
        print(f"[Chroma 向量库]   论文数: {len(titles)}  | chunk 总数: {vs.total_chunks}")
        for t in titles:
            print(f"    - {t}")
    except Exception as e:
        print(f"[Chroma 向量库]   读取失败: {e}")

    # 2. Neo4j 图谱
    try:
        from graph.neo4j_store import GraphStore
        gs = GraphStore()
        if gs.available:
            stats = gs.get_stats(user_id=user_id or "system")
            nodes = stats.get("nodes", {})
            print(f"[Neo4j 图谱]      Paper: {nodes.get('Paper', 0)} | 全部节点: {nodes} | 关系: {stats.get('total_edges', 0)}")
        else:
            print("[Neo4j 图谱]      不可用（连接失败）")
        gs.close()
    except Exception as e:
        print(f"[Neo4j 图谱]      读取失败: {e}")

    # 3. SQLite 各表
    try:
        conn = sqlite3.connect(DB_PATH)
        for table in ("paper_status", "annotations", "upload_logs"):
            try:
                if user_id:
                    n = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
                    ).fetchone()[0]
                else:
                    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"[SQLite:{table}]  记录数: {n}")
            except sqlite3.OperationalError:
                print(f"[SQLite:{table}]  表不存在")
        conn.close()
    except Exception as e:
        print(f"[SQLite]          读取失败: {e}")

    # 4. PDF 物理文件
    try:
        if os.path.isdir(UPLOAD_DIR):
            pdfs = []
            for root, _, files in os.walk(UPLOAD_DIR):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        pdfs.append(os.path.join(root, f))
            print(f"[PDF 文件]        数量: {len(pdfs)}")
            for p in pdfs:
                print(f"    - {os.path.relpath(p, BASE_DIR)}")
        else:
            print("[PDF 文件]        目录不存在")
    except Exception as e:
        print(f"[PDF 文件]        读取失败: {e}")

    print("=" * 60)


# ---------------- 清理 ----------------

def clean(user_id: str | None):
    print("=" * 60)
    print("开始清理残留数据" + (f"（用户: {user_id}）" if user_id else "（所有用户）"))
    print("=" * 60)

    # 1. Chroma 向量库
    try:
        from store.vector_store import VectorStore
        vs = VectorStore()
        titles = vs.list_papers(user_id=user_id)
        for t in titles:
            vs.delete_paper(t, user_id=user_id)
        print(f"✓ Chroma: 删除了 {len(titles)} 篇论文的向量")
    except Exception as e:
        print(f"✗ Chroma 清理失败: {e}")

    # 2. Neo4j 图谱
    try:
        from graph.neo4j_store import GraphStore
        gs = GraphStore()
        if gs.available:
            gs.clear_all(user_id=user_id)
            print("✓ Neo4j: 已清空" + (f"用户 {user_id} 的" if user_id else "所有") + "节点与关系")
        else:
            print("✗ Neo4j 不可用，跳过（这可能正是残留的原因，请确认 Neo4j 已启动后重跑）")
        gs.close()
    except Exception as e:
        print(f"✗ Neo4j 清理失败: {e}")

    # 3. SQLite 各表
    try:
        conn = sqlite3.connect(DB_PATH)
        for table in ("paper_status", "annotations", "upload_logs"):
            try:
                if user_id:
                    conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                else:
                    conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()
        print("✓ SQLite: 已清理 paper_status / annotations / upload_logs")
    except Exception as e:
        print(f"✗ SQLite 清理失败: {e}")

    # 4. PDF 物理文件
    try:
        target_dir = os.path.join(UPLOAD_DIR, user_id) if user_id else UPLOAD_DIR
        removed = 0
        if os.path.isdir(target_dir):
            for root, _, files in os.walk(target_dir):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        os.remove(os.path.join(root, f))
                        removed += 1
        print(f"✓ PDF 文件: 删除了 {removed} 个")
    except Exception as e:
        print(f"✗ PDF 文件清理失败: {e}")

    print("=" * 60)
    print("清理完成。请刷新前端页面确认。")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="残留论文数据诊断/清理")
    parser.add_argument("--clean", action="store_true", help="执行清理（默认只诊断）")
    parser.add_argument("--user", default=None, help="只针对指定 user_id 操作")
    args = parser.parse_args()

    if args.clean:
        diagnose(args.user)
        confirm = input("\n以上数据将被删除，确认清理？输入 yes 继续: ").strip().lower()
        if confirm == "yes":
            clean(args.user)
        else:
            print("已取消。")
    else:
        diagnose(args.user)
        print("\n提示：如需清理，运行  python cleanup_residual.py --clean")
