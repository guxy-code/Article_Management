"""
RAG 问答链
检索相关 chunk → 拼入 prompt → LLM 生成回答
"""

import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from store.vector_store import VectorStore


# RAG prompt 模板
RAG_PROMPT_TEMPLATE = """你是一个专业的学术论文助手，帮助研究生理解和检索论文内容。

请根据以下检索到的论文片段来回答用户的问题。

**规则：**
1. 只根据提供的论文片段回答，不要编造内容
2. 如果片段中没有相关信息，明确告诉用户"在已有论文中未找到相关内容"
3. 回答时注明来源论文的标题
4. 用中文回答，但专业术语保留英文

**检索到的论文片段：**
{context}

**用户问题：**
{question}

**回答：**"""


class PaperQAChain:
    """论文问答链：检索 + LLM 生成"""

    def __init__(
        self,
        vector_store: VectorStore,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.vector_store = vector_store

        # LLM 配置
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

        # 构建 prompt
        self.prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

        # 构建 chain
        self.chain = self.prompt | self.llm | StrOutputParser()

    def ask(self, question: str, k: int = 5) -> str:
        """
        提问并获得基于论文内容的回答。

        Args:
            question: 用户问题
            k: 检索的 chunk 数量

        Returns:
            LLM 生成的回答
        """
        # 1. 检索相关 chunk
        docs = self.vector_store.search(question, k=k)

        if not docs:
            return "📭 知识库为空或未找到相关内容。请先上传论文。"

        # 2. 拼接上下文
        context = self._format_context(docs)

        # 3. 调用 LLM 生成回答
        answer = self.chain.invoke({
            "context": context,
            "question": question,
        })

        return answer

    def ask_with_sources(self, question: str, k: int = 5) -> dict:
        """
        提问并返回回答 + 来源信息。

        Returns:
            {"answer": str, "sources": [{"title": str, "chunk": str}]}
        """
        docs = self.vector_store.search(question, k=k)

        if not docs:
            return {
                "answer": "📭 知识库为空或未找到相关内容。请先上传论文。",
                "sources": [],
            }

        context = self._format_context(docs)

        answer = self.chain.invoke({
            "context": context,
            "question": question,
        })

        sources = [
            {
                "title": doc.metadata.get("title", "未知"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "content_preview": doc.page_content[:150] + "...",
            }
            for doc in docs
        ]

        return {"answer": answer, "sources": sources}

    def _format_context(self, docs: list[Document]) -> str:
        """将检索到的文档格式化为上下文字符串"""
        parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "未知论文")
            parts.append(
                f"--- 片段 {i} (来源: {title}) ---\n{doc.page_content}"
            )
        return "\n\n".join(parts)
