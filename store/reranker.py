"""
LLM Batch 重排序器
用 LLM 对候选文档按相关性排序，一次调用完成。
"""

import os
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document


RERANK_PROMPT_TEMPLATE = """你是一个学术文档相关性排序专家。请对以下文档片段按与查询的相关性从高到低排序。

查询：{query}

候选文档：
{candidates}

请只输出排序后的文档编号（从最相关到最不相关），用逗号分隔。例如：3,1,5,2,4

排序结果："""


class LLMReranker:
    """基于 LLM 的 Batch 重排序器"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )
        self.prompt = ChatPromptTemplate.from_template(RERANK_PROMPT_TEMPLATE)
        self.chain = self.prompt | self.llm | StrOutputParser()

    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        """
        对候选文档重排序。

        策略：
        - 如果候选数 <= top_k，跳过重排序
        - 每个文档截断到 200 字送评分
        - 一次 LLM 调用，输出排序编号
        - 解析编号，按新顺序返回 top_k

        Args:
            query: 检索查询
            documents: 候选文档列表
            top_k: 返回的文档数量

        Returns:
            重排序后的 top_k 文档列表
        """
        if len(documents) <= top_k:
            return documents

        # 构建候选文本（每个截断到 200 字）
        candidates_text = self._format_candidates(documents)

        try:
            result = self.chain.invoke({
                "query": query,
                "candidates": candidates_text,
            })

            # 解析排序结果
            ranked_indices = self._parse_ranking(result, len(documents))

            # 按排序取 top_k
            ranked_docs = []
            for idx in ranked_indices[:top_k]:
                if 0 <= idx < len(documents):
                    ranked_docs.append(documents[idx])

            # 如果解析不完整，补充剩余文档
            if len(ranked_docs) < top_k:
                remaining = [d for d in documents if d not in ranked_docs]
                ranked_docs.extend(remaining[:top_k - len(ranked_docs)])

            return ranked_docs

        except Exception:
            # 重排失败，降级返回前 top_k
            return documents[:top_k]

    def _format_candidates(self, documents: list[Document]) -> str:
        """格式化候选文档，每个截断到 200 字"""
        parts = []
        for i, doc in enumerate(documents, 1):
            content = doc.page_content[:200]
            if len(doc.page_content) > 200:
                content += "..."
            title = doc.metadata.get("title", "未知")
            parts.append(f"[{i}] (来源: {title}) {content}")
        return "\n\n".join(parts)

    def _parse_ranking(self, result: str, total: int) -> list[int]:
        """
        解析 LLM 输出的排序编号。
        例如 "3,1,5,2,4" → [2, 0, 4, 1, 3]（转为 0-indexed）
        """
        # 提取所有数字
        numbers = re.findall(r"\d+", result)
        indices = []
        seen = set()

        for num_str in numbers:
            idx = int(num_str) - 1  # 转为 0-indexed
            if 0 <= idx < total and idx not in seen:
                indices.append(idx)
                seen.add(idx)

        return indices
