"""
Semantic Scholar API 调用模块
搜索论文，返回结构化结果。带内存缓存避免重复请求。
"""

import time
import requests
from datetime import datetime


API_BASE = "https://api.semanticscholar.org/graph/v1"

# 内存缓存：key → (timestamp, results)
_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL = 3600  # 1 小时过期


def search_papers(
    keywords: list[str],
    year_from: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    使用 Semantic Scholar API 搜索论文（带缓存）。
    """
    query = " ".join(keywords)

    # 检查缓存
    cache_key = f"{query}|{year_from}|{limit}"
    if cache_key in _cache:
        cached_time, cached_results = _cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return cached_results

    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,url,openAccessPdf",
    }

    if year_from:
        params["year"] = f"{year_from}-"

    try:
        resp = requests.get(
            f"{API_BASE}/paper/search",
            params=params,
            timeout=15,
        )

        # 如果被限流，等 3 秒重试一次
        if resp.status_code == 429:
            time.sleep(3)
            resp = requests.get(
                f"{API_BASE}/paper/search",
                params=params,
                timeout=15,
            )

        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"⚠️ Semantic Scholar API 请求失败: {e}")
        return []

    papers = []
    for item in data.get("data", []):
        authors = [a.get("name", "") for a in item.get("authors", [])[:4]]
        url = item.get("url", "")
        if item.get("openAccessPdf"):
            url = item["openAccessPdf"].get("url", url)

        papers.append({
            "title": item.get("title", ""),
            "authors": authors,
            "year": item.get("year"),
            "venue": item.get("venue", ""),
            "url": url,
        })

    # 存入缓存
    _cache[cache_key] = (time.time(), papers)

    return papers


def get_recommendation_keywords(graph_store, memory_store=None, interest_graph=None, user_id: str = "system") -> list[str]:
    """
    推荐关键词来源（按优先级）：
    1. 用户兴趣图谱：取 weight 高但 hit_count 较低的节点（有兴趣但还在探索的方向）
    2. 记忆库 topics 频率统计
    3. Neo4j concept 频率（回退）
    """
    # 优先：用户兴趣图谱（探索中的方向）
    if interest_graph is not None and interest_graph.available:
        try:
            # 取 Top Field
            top_fields = interest_graph.get_top_nodes(user_id, type="Field", limit=2)
            exploring = []
            for field in top_fields:
                children = interest_graph.get_children(field["name"], user_id, limit=10)
                for child in children:
                    # 有兴趣（weight > 0.2）但还在探索（hit_count < 5）
                    if (child.get("hit_count") or 0) < 5 and (child.get("weight") or 0) > 0.2:
                        exploring.append(child["name"])
            if exploring:
                return exploring[:5]
            # 无探索中的方向 → 取 Top 节点名
            top_all = interest_graph.get_top_nodes(user_id, limit=5)
            if top_all:
                return [n["name"] for n in top_all]
        except Exception:
            pass

    # 回退：记忆库 topics 频率
    if memory_store is not None:
        try:
            top_topics = memory_store.get_top_topics(user_id, limit=5)
            if top_topics:
                return top_topics
        except Exception:
            pass

    # 最终回退：Neo4j 概念频率
    try:
        freq = graph_store.get_concept_frequency(user_id=user_id)
        return [c["name"] for c in freq[:3]]
    except Exception:
        return []
