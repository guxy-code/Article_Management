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


def get_recommendation_keywords(graph_store) -> list[str]:
    """从 Neo4j 获取 Top 3 Concept 作为推荐关键词"""
    try:
        freq = graph_store.get_concept_frequency()
        return [c["name"] for c in freq[:3]]
    except Exception:
        return []
