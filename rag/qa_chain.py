"""
RAG 问答链
检索相关 chunk → 拼入 prompt → LLM 生成回答

支持两种模式：
1. 单次问答（无历史）— ask_with_sources()
2. 多轮对话（带 session）— ask_with_session()
"""

import os
import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from store.vector_store import VectorStore
from store.hybrid_retriever import HybridRetriever
from rag.session_store import SessionStore
from rag.query_rewriter import QueryRewriter
from rag.conversation_memory import ConversationMemory
from rag.graph_retriever import GraphRetriever


# 单次问答 prompt（向后兼容）
RAG_PROMPT_TEMPLATE = """你是一个专业的学术论文助手，帮助研究生理解和检索论文内容。

请根据以下检索到的论文片段和知识图谱关系来回答用户的问题。

**规则：**
1. 优先使用知识图谱中的结构化关系回答关系性问题
2. 使用论文片段补充细节和原文依据
3. 如果都没有相关信息，明确告诉用户"在已有论文中未找到相关内容"
4. 回答时注明来源论文的标题
5. 用中文回答，但专业术语保留英文

{graph_context}

**检索到的论文片段：**
{context}

**用户问题：**
{question}

**回答：**"""


# 多轮对话 prompt
CONVERSATIONAL_RAG_PROMPT = """你是一个专业的学术论文助手，帮助研究生理解和检索论文内容。

请根据对话历史、知识图谱关系和检索到的论文片段来回答用户的问题。

**规则：**
1. 优先使用知识图谱中的结构化关系回答关系性问题
2. 使用论文片段补充细节和原文依据
3. 如果都没有相关信息，明确告诉用户"在已有论文中未找到相关内容"
4. 回答时注明来源论文的标题
5. 用中文回答，但专业术语保留英文
6. 参考对话历史保持回答的连贯性，避免重复已说过的内容
7. 如果用户的问题是对之前回答的追问，结合之前的上下文回答

**对话历史：**
{chat_history}

{graph_context}

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
        hybrid_retriever: Optional[HybridRetriever] = None,
        session_store: Optional[SessionStore] = None,
        graph_retriever: Optional[GraphRetriever] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.vector_store = vector_store
        self.hybrid_retriever = hybrid_retriever  # 可选，None 时降级为纯向量检索
        self.session_store = session_store or SessionStore()
        self.graph_retriever = graph_retriever  # 可选，图谱增强检索

        # LLM 配置
        self.llm = ChatOpenAI(
            model=model_name or os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

        # 单次问答 chain
        self.prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
        self.chain = self.prompt | self.llm | StrOutputParser()

        # 多轮对话 chain
        self.conv_prompt = ChatPromptTemplate.from_template(CONVERSATIONAL_RAG_PROMPT)
        self.conv_chain = self.conv_prompt | self.llm | StrOutputParser()

        # 子模块
        self.query_rewriter = QueryRewriter(
            model_name=model_name, api_key=api_key, base_url=base_url
        )
        self.memory = ConversationMemory(
            model_name=model_name, api_key=api_key, base_url=base_url
        )

    def ask(self, question: str, k: int = 5) -> str:
        """
        单次提问（向后兼容，无对话历史）。
        """
        docs = self.vector_store.search(question, k=k)

        if not docs:
            return "📭 知识库为空或未找到相关内容。请先上传论文。"

        context = self._format_context(docs)
        answer = self.chain.invoke({
            "context": context,
            "question": question,
        })
        return answer

    def ask_with_sources(self, question: str, k: int = 5) -> dict:
        """
        单次提问 + 返回来源（向后兼容）。
        现在同时查询向量库和知识图谱。
        """
        docs = self.vector_store.search(question, k=k)

        if not docs:
            return {
                "answer": "📭 知识库为空或未找到相关内容。请先上传论文。",
                "sources": [],
            }

        context = self._format_context(docs)

        # 图谱增强：查询结构化关系
        graph_context = ""
        if self.graph_retriever:
            try:
                graph_context = self.graph_retriever.retrieve(question)
            except Exception:
                graph_context = ""

        answer = self.chain.invoke({
            "context": context,
            "graph_context": graph_context,
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

    def ask_with_session(self, question: str, session_id: str, k: int = 5) -> dict:
        """
        多轮对话 RAG 问答。

        流程：
        1. 从 session_store 获取历史 + 摘要
        2. Query 改写（解决指代问题）
        3. 用改写后的 query 向量检索
        4. 动态分配 budget
        5. 组装 prompt（摘要 + 最近历史 + chunks + question）
        6. LLM 生成回答
        7. 存储本轮 Q&A
        8. 条件触发摘要更新

        Returns:
            {"answer": str, "sources": list, "rewritten_query": str}
        """
        # 1. 获取会话历史和摘要
        session = self.session_store.get_session(session_id)
        if not session:
            return self.ask_with_sources(question, k=k)

        messages = self.session_store.get_messages(session_id)
        summary = session.get("summary", "")

        # 2. Query 改写（同时提取论文限定）
        recent_for_rewrite = self.memory.format_for_rewrite(messages, max_turns=2)
        rewrite_result = self.query_rewriter.rewrite(question, recent_for_rewrite)
        rewritten_query = rewrite_result["query"]
        filter_title = rewrite_result.get("filter_title")

        # 3. 检索（优先用混合检索器）
        if self.hybrid_retriever:
            docs = self.hybrid_retriever.search(
                rewritten_query, k=k, filter_title=filter_title
            )
        else:
            # 降级为纯向量检索
            if filter_title:
                docs = self.vector_store.search_with_filter(
                    rewritten_query, k=k, filter_dict={"title": filter_title}
                )
            else:
                docs = self.vector_store.search(rewritten_query, k=k)

        if not docs:
            # 无检索结果时仍存储对话
            answer = "📭 知识库为空或未找到相关内容。请先上传论文。"
            self.session_store.add_message(session_id, "user", question)
            self.session_store.add_message(session_id, "assistant", answer, "[]")
            if len(messages) == 0:
                self.session_store.update_title(session_id, question[:40])
            return {"answer": answer, "sources": [], "rewritten_query": rewritten_query}

        # 4. Budget 分配
        chunks_text = self._format_context(docs)
        budget = self.memory.calculate_budget(chunks_text)

        # 5. 格式化历史
        chat_history = self.memory.format_for_prompt(
            messages, summary, budget["history_budget"]
        )

        # 6. 图谱增强检索
        graph_context = ""
        if self.graph_retriever:
            try:
                graph_context = self.graph_retriever.retrieve(question)
            except Exception:
                graph_context = ""

        # 7. LLM 生成回答
        if chat_history:
            answer = self.conv_chain.invoke({
                "chat_history": chat_history,
                "graph_context": graph_context,
                "context": chunks_text,
                "question": question,
            })
        else:
            # 首条消息，无历史，用简单 prompt
            answer = self.chain.invoke({
                "graph_context": graph_context,
                "context": chunks_text,
                "question": question,
            })

        # 构建 sources
        sources = [
            {
                "title": doc.metadata.get("title", "未知"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "content_preview": doc.page_content[:150] + "...",
            }
            for doc in docs
        ]

        # 7. 存储本轮 Q&A
        self.session_store.add_message(session_id, "user", question)
        self.session_store.add_message(
            session_id, "assistant", answer, json.dumps(sources, ensure_ascii=False)
        )

        # 自动生成标题（首次对话时）
        if len(messages) == 0:
            title = question[:40] + ("..." if len(question) > 40 else "")
            self.session_store.update_title(session_id, title)

        # 8. 条件触发摘要更新（每 3 轮）
        new_message_count = len(messages) + 2  # 加上刚存的 user + assistant
        if self.memory.should_update_summary(new_message_count):
            all_messages = self.session_store.get_messages(session_id)
            new_summary = self.memory.generate_summary(all_messages)
            if new_summary:
                self.session_store.update_summary(session_id, new_summary)

        return {
            "answer": answer,
            "sources": sources,
            "rewritten_query": rewritten_query,
        }

    def _format_context(self, docs: list[Document]) -> str:
        """将检索到的文档格式化为上下文字符串"""
        parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "未知论文")
            parts.append(
                f"--- 片段 {i} (来源: {title}) ---\n{doc.page_content}"
            )
        return "\n\n".join(parts)

    async def ask_with_session_stream(self, question: str, session_id: str, k: int = 5):
        """
        流式版多轮对话 RAG 问答。

        前置步骤（改写、检索、rerank）仍阻塞执行，
        只有 LLM 生成阶段改为逐 token yield。

        Yields:
            {"type": "sources", "data": [...]}   — 检索完成后立即返回来源
            {"type": "token", "data": "字"}      — 逐 token 流式
            {"type": "done", "data": "完整回答"}  — 生成结束
            {"type": "error", "data": "错误信息"} — 出错时
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # 1. 获取会话历史和摘要
        session = self.session_store.get_session(session_id)
        if not session:
            yield {"type": "sources", "data": []}
            yield {"type": "done", "data": "📭 会话不存在，请创建新会话。"}
            return

        messages = self.session_store.get_messages(session_id)
        summary = session.get("summary", "")

        # 2. Query 改写
        recent_for_rewrite = self.memory.format_for_rewrite(messages, max_turns=2)
        rewrite_result = self.query_rewriter.rewrite(question, recent_for_rewrite)
        rewritten_query = rewrite_result["query"]
        filter_title = rewrite_result.get("filter_title")

        # 3. 检索
        if self.hybrid_retriever:
            docs = self.hybrid_retriever.search(
                rewritten_query, k=k, filter_title=filter_title
            )
        else:
            if filter_title:
                docs = self.vector_store.search_with_filter(
                    rewritten_query, k=k, filter_dict={"title": filter_title}
                )
            else:
                docs = self.vector_store.search(rewritten_query, k=k)

        # 构建 sources
        sources = [
            {
                "title": doc.metadata.get("title", "未知"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "content_preview": doc.page_content[:150] + "...",
            }
            for doc in docs
        ]

        # 立即 yield sources
        yield {"type": "sources", "data": sources}

        if not docs:
            answer = "📭 知识库为空或未找到相关内容。请先上传论文。"
            self.session_store.add_message(session_id, "user", question)
            self.session_store.add_message(session_id, "assistant", answer, "[]")
            if len(messages) == 0:
                self.session_store.update_title(session_id, question[:40])
            yield {"type": "done", "data": answer}
            return

        # 4. Budget 分配
        chunks_text = self._format_context(docs)
        budget = self.memory.calculate_budget(chunks_text)

        # 5. 格式化历史
        chat_history = self.memory.format_for_prompt(
            messages, summary, budget["history_budget"]
        )

        # 6. 图谱增强检索
        graph_context = ""
        if self.graph_retriever:
            try:
                graph_context = self.graph_retriever.retrieve(question)
            except Exception:
                graph_context = ""

        # 7. 构造 prompt（手动构建，不用 chain，以便流式调用 llm）
        if chat_history:
            prompt_text = CONVERSATIONAL_RAG_PROMPT.format(
                chat_history=chat_history,
                graph_context=graph_context,
                context=chunks_text,
                question=question,
            )
        else:
            prompt_text = RAG_PROMPT_TEMPLATE.format(
                graph_context=graph_context,
                context=chunks_text,
                question=question,
            )

        # 7. LLM 流式生成
        full_answer = ""
        try:
            async for chunk in self.llm.astream([HumanMessage(content=prompt_text)]):
                token = chunk.content
                if token:
                    full_answer += token
                    yield {"type": "token", "data": token}
        except Exception as e:
            yield {"type": "error", "data": str(e)}
            return

        yield {"type": "done", "data": full_answer}

        # 8. 存储本轮 Q&A
        self.session_store.add_message(session_id, "user", question)
        self.session_store.add_message(
            session_id, "assistant", full_answer, json.dumps(sources, ensure_ascii=False)
        )

        # 自动生成标题
        if len(messages) == 0:
            title = question[:40] + ("..." if len(question) > 40 else "")
            self.session_store.update_title(session_id, title)

        # 条件触发摘要更新
        new_message_count = len(messages) + 2
        if self.memory.should_update_summary(new_message_count):
            all_messages = self.session_store.get_messages(session_id)
            new_summary = self.memory.generate_summary(all_messages)
            if new_summary:
                self.session_store.update_summary(session_id, new_summary)
