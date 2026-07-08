"""
Query 改写模块
将含有指代词的短问题改写为独立的、适合向量检索的完整 query。
"""

import os
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


REWRITE_PROMPT_TEMPLATE = """你是一个查询改写助手。根据对话上下文，将用户最新的问题改写为一个独立的、完整的学术检索查询。

规则：
1. 解析所有代词和指代（"它"、"这个方法"、"上面提到的"、"第二点"等）
2. 保留学术术语的英文原文
3. 如果问题已经是独立完整的，直接返回原问题
4. 如果用户明确提到某篇论文（如"在那篇XX论文里"、"这篇论文的"），提取论文关键词
5. 严格按照以下格式输出两行（不要加其他内容）：

查询：[改写后的检索查询]
论文：[论文标题关键词，如果未指定则写"无"]

对话上下文：
{recent_history}

用户最新问题：{question}
"""


# 判断是否需要改写的模式
PRONOUN_PATTERNS = re.compile(
    r"(它|这个|那个|这篇|那篇|该|其|上面|前面|之前|刚才|"
    r"这种|那种|此|这些|那些|第[一二三四五六七八九十\d]+|"
    r"this|that|it|they|these|those|the above|mentioned)",
    re.IGNORECASE,
)


class QueryRewriter:
    """LLM Query 改写器"""

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
        self.prompt = ChatPromptTemplate.from_template(REWRITE_PROMPT_TEMPLATE)
        self.chain = self.prompt | self.llm | StrOutputParser()

    def needs_rewrite(self, question: str) -> bool:
        """
        判断是否需要改写。
        - 问题较短（<30字）且含代词/指代 → 需要改写
        - 问题较长且独立 → 不需要
        """
        if len(question) > 60 and not PRONOUN_PATTERNS.search(question):
            return False
        if PRONOUN_PATTERNS.search(question):
            return True
        if len(question) < 15:
            return True
        return False

    def rewrite(self, question: str, recent_history: str) -> dict:
        """
        改写 query 并提取论文限定。

        Args:
            question: 用户当前问题
            recent_history: 格式化后的最近 2 轮对话文本

        Returns:
            {"query": str, "filter_title": str | None}
        """
        if not recent_history.strip():
            return {"query": question, "filter_title": None}

        if not self.needs_rewrite(question):
            return {"query": question, "filter_title": None}

        try:
            result = self.chain.invoke({
                "recent_history": recent_history,
                "question": question,
            })

            # 解析输出
            return self._parse_rewrite_result(result, question)

        except Exception:
            # 改写失败时降级为原始 query
            return {"query": question, "filter_title": None}

    def _parse_rewrite_result(self, result: str, original_question: str) -> dict:
        """解析改写结果，提取 query 和 filter_title"""
        query = original_question
        filter_title = None

        lines = result.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("查询：") or line.startswith("查询:"):
                q = line.split("：", 1)[-1].split(":", 1)[-1].strip().strip('"').strip("'")
                if q:
                    query = q
            elif line.startswith("论文：") or line.startswith("论文:"):
                p = line.split("：", 1)[-1].split(":", 1)[-1].strip().strip('"').strip("'")
                if p and p != "无" and p != "无。":
                    filter_title = p

        return {"query": query, "filter_title": filter_title}
