"""
混合检索器
融合向量检索 + BM25 关键词检索，支持 metadata 过滤和 LLM 重排序。
"""

from typing import Optional
from langchain_core.documents import Document

from store.vector_store import VectorStore
from store.bm25_store import BM25Store
from store.reranker import LLMReranker


class HybridRetriever:
    """混合检索器：向量 + BM25 + Metadata 过滤 + 重排序"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        reranker: Optional[LLMReranker] = None,
    ):
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.reranker = reranker

    def search(
        self,
        query: str,
        k: int = 5,
        filter_title: Optional[str] = None,
        filter_titles: Optional[list[str]] = None,
        use_rerank: bool = True,
    ) -> list[Document]:
        """
        完整混合检索流程：

        1. 向量检索 top-N（可带 metadata filter）
        2. BM25 检索 top-N
        3. RRF 融合
        4. 可选 LLM 重排序
        5. 返回 top-k

        Args:
            query: 检索查询（应为经过 query rewrite 的独立查询）
            k: 最终返回结果数
            filter_title: 单篇论文过滤（向后兼容）
            filter_titles: 多篇论文过滤列表，优先级高于 filter_title
            use_rerank: 是否启用重排序

        Returns:
            最终 top-k 文档列表
        """
        fetch_k = k * 4  # 粗筛数量

        # 合并 filter_title / filter_titles 为统一的 titles 列表
        effective_titles: Optional[list[str]] = None
        if filter_titles:
            effective_titles = filter_titles
        elif filter_title:
            effective_titles = [filter_title]

        # 构建 Chroma filter
        title_filter = self.vector_store.build_title_filter(effective_titles) if effective_titles else None

        # 1. 向量检索
        if title_filter:
            vector_results = self.vector_store.search_with_filter(
                query, k=fetch_k, filter_dict=title_filter
            )
        else:
            vector_results = self.vector_store.search(query, k=fetch_k)

        # 2. BM25 检索（全库，后续 RRF 融合时自然排序会体现相关性）
        bm25_results_with_scores = self.bm25_store.search(query, k=fetch_k)
        bm25_results = [doc for doc, _ in bm25_results_with_scores]

        # 如果有论文过滤，对 BM25 结果也做同样过滤
        if effective_titles:
            titles_set = set(effective_titles)
            bm25_results = [
                doc for doc in bm25_results
                if doc.metadata.get("title") in titles_set
            ]

        # 3. RRF 融合
        fused = self._rrf_fusion(vector_results, bm25_results)

        # 4. 重排序
        if use_rerank and self.reranker and len(fused) > k:
            final_results = self.reranker.rerank(query, fused, top_k=k)
        else:
            final_results = fused[:k]

        return final_results

    def _rrf_fusion(
        self,
        vector_results: list[Document],
        bm25_results: list[Document],
        rrf_k: int = 60,
    ) -> list[Document]:
        """
        Reciprocal Rank Fusion 融合两路检索结果。

        RRF_score(d) = 1/(rrf_k + rank_vector(d)) + 1/(rrf_k + rank_bm25(d))

        Args:
            vector_results: 向量检索结果（已按相似度排序）
            bm25_results: BM25 检索结果（已按分数排序）
            rrf_k: RRF 参数，默认 60（经典值）

        Returns:
            融合后按 RRF 分数降序排列的文档列表
        """
        # 用 page_content + title 作为文档唯一标识
        def doc_key(doc: Document) -> str:
            title = doc.metadata.get("title", "")
            chunk_idx = doc.metadata.get("chunk_index", -1)
            return f"{title}::{chunk_idx}"

        # 计算 RRF 分数
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(vector_results):
            key = doc_key(doc)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (rrf_k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_results):
            key = doc_key(doc)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (rrf_k + rank + 1)
            doc_map[key] = doc

        # 按 RRF 分数降序排列
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

        return [doc_map[key] for key in sorted_keys]
