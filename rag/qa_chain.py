"""
RAG 问答链
检索相关 chunk → 拼入 prompt → LLM 生成回答

支持两种模式：
1. 单次问答（无历史）— ask_with_sources()
2. 多轮对话（带 session）— ask_with_session()
"""

import os
import json
import asyncio
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
{paper_scope}
{profile_context}
{memory_context}
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
{paper_scope}
{profile_context}
{memory_context}
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
        memory_retriever=None,
        memory_distiller=None,
        profile_builder=None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.vector_store = vector_store
        self.hybrid_retriever = hybrid_retriever  # 可选，None 时降级为纯向量检索
        self.session_store = session_store or SessionStore()
        self.graph_retriever = graph_retriever  # 可选，图谱增强检索
        self.memory_retriever = memory_retriever  # 可选，自生长记忆检索
        self.memory_distiller = memory_distiller  # 可选，自生长记忆蒸馏
        self.profile_builder = profile_builder  # 可选，用户画像构建
        self.interest_distiller = None  # 可选，用户兴趣图谱蒸馏（由 server.py 注入）
        self.interest_retriever = None  # 可选，用户兴趣图谱检索注入（由 server.py 注入）

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
            "graph_context": "",
            "memory_context": "",
            "profile_context": "",
            "paper_scope": "",
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
            "memory_context": "",
            "profile_context": "",
            "question": question,
            "paper_scope": "",
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

    async def ask_with_session(self, question: str, session_id: str, k: int = 5,
                         paper_title: Optional[str] = None,
                         paper_titles: Optional[list[str]] = None,
                         user_id: Optional[str] = None) -> dict:
        """
        多轮对话 RAG 问答。

        Args:
            paper_title: 单篇论文过滤（来自 PDF 阅读器，向后兼容）
            paper_titles: 多篇论文过滤列表（来自 Chat 页面的论文选择器）
            user_id: 当前用户 ID，用于数据隔离
        """
        # 合并：paper_title 优先（PDF 阅读器场景），然后是 paper_titles
        effective_titles: Optional[list[str]] = None
        if paper_title:
            effective_titles = [paper_title]
        elif paper_titles:
            effective_titles = paper_titles

        # 1. 获取会话历史和摘要
        session = self.session_store.get_session(session_id, user_id)
        if not session:
            return self.ask_with_sources(question, k=k)

        messages = self.session_store.get_messages(session_id)
        summary = session.get("summary", "")

        # 2. Query 改写
        recent_for_rewrite = self.memory.format_for_rewrite(messages, max_turns=2)
        rewrite_result = self.query_rewriter.rewrite(question, recent_for_rewrite)
        rewritten_query = rewrite_result["query"]
        if not effective_titles:
            filter_hint = rewrite_result.get("filter_title")
            if filter_hint:
                effective_titles = [filter_hint]

        # 3. 检索
        if self.hybrid_retriever:
            docs = self.hybrid_retriever.search(
                rewritten_query, k=k,
                filter_titles=effective_titles,
                user_id=user_id,
            )
        else:
            title_filter = (
                self.vector_store.build_title_filter(effective_titles, user_id=user_id)
                if effective_titles else ({"user_id": user_id} if user_id else None)
            )
            if title_filter:
                docs = self.vector_store.search_with_filter(
                    rewritten_query, k=k, filter_dict=title_filter
                )
            else:
                docs = self.vector_store.search(rewritten_query, k=k)

        if not docs:
            answer = "📭 知识库为空或未找到相关内容。请先上传论文。"
            self.session_store.add_message(session_id, "user", question)
            self.session_store.add_message(session_id, "assistant", answer, "[]")
            if len(messages) == 0:
                self.session_store.update_title(session_id, question[:40])
            return {"answer": answer, "sources": [], "rewritten_query": rewritten_query}

        chunks_text = self._format_context(docs)
        budget = self.memory.calculate_budget(chunks_text)
        chat_history = self.memory.format_for_prompt(messages, summary, budget["history_budget"])

        graph_context = ""
        if self.graph_retriever:
            try:
                graph_context = self.graph_retriever.retrieve(question, user_id=user_id)
            except Exception:
                graph_context = ""

        # 自生长记忆：检索相关记忆并注入（同步，无 LLM）
        injected_memories = self._retrieve_memories(question, user_id)
        memory_context = self._format_memory_context(injected_memories)
        # 用户画像：读缓存注入（同步，无 LLM）+ 惰性触发重算
        profile_context = self._get_profile_context(user_id)
        # 用户兴趣图谱：检索相关节点注入（同步，无 LLM）
        interest_context = self._get_interest_context(question, user_id)
        if interest_context:
            profile_context = (profile_context + "\n" + interest_context) if profile_context else interest_context

        if paper_title:
            paper_scope = (
                f"\n**当前阅读论文：** 用户正在阅读《{paper_title}》，请优先针对该论文回答，代词如'这个方法'、'该算法'均指该论文中的内容。\n"
            )
        elif effective_titles and len(effective_titles) > 0:
            titles_str = "、".join(f"《{t}》" for t in effective_titles)
            paper_scope = f"\n**检索范围限定：** 用户已将检索范围限定在以下论文：{titles_str}，请优先从这些论文中回答。\n"
        else:
            paper_scope = ""

        if chat_history:
            answer = self.conv_chain.invoke({
                "chat_history": chat_history,
                "graph_context": graph_context,
                "memory_context": memory_context,
                "profile_context": profile_context,
                "context": chunks_text,
                "question": question,
                "paper_scope": paper_scope,
            })
        else:
            answer = self.chain.invoke({
                "graph_context": graph_context,
                "memory_context": memory_context,
                "profile_context": profile_context,
                "context": chunks_text,
                "question": question,
                "paper_scope": paper_scope,
            })

        sources = [
            {
                "title": doc.metadata.get("title", "未知"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "content_preview": doc.page_content[:150] + "...",
            }
            for doc in docs
        ]

        self.session_store.add_message(session_id, "user", question)
        self.session_store.add_message(
            session_id, "assistant", answer, json.dumps(sources, ensure_ascii=False)
        )

        if len(messages) == 0:
            title = question[:40] + ("..." if len(question) > 40 else "")
            self.session_store.update_title(session_id, title)

        new_message_count = len(messages) + 2
        if self.memory.should_update_summary(new_message_count):
            all_messages = self.session_store.get_messages(session_id)
            new_summary = self.memory.generate_summary(all_messages)
            if new_summary:
                self.session_store.update_summary(session_id, new_summary)

        # 自生长记忆：问答后 fire-and-forget 蒸馏（不阻塞返回）
        self._trigger_distill(question, answer, sources, session_id, user_id, injected_memories)

        return {"answer": answer, "sources": sources, "rewritten_query": rewritten_query}

    def _format_context(self, docs: list[Document]) -> str:
        """将检索到的文档格式化为上下文字符串"""
        parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "未知论文")
            parts.append(
                f"--- 片段 {i} (来源: {title}) ---\n{doc.page_content}"
            )
        return "\n\n".join(parts)

    # ================= 自生长记忆辅助方法 =================

    def _retrieve_memories(self, question: str, user_id: Optional[str]) -> list[dict]:
        """检索相关记忆（同步，无 LLM）。未启用或失败返回空列表。"""
        if not self.memory_retriever or not user_id:
            return []
        try:
            return self.memory_retriever.retrieve(question, user_id=user_id)
        except Exception:
            return []

    def _format_memory_context(self, memories: list[dict]) -> str:
        """把记忆列表格式化为注入 prompt 的文本块。空或失败返回空字符串。"""
        if not memories or not self.memory_retriever:
            return ""
        try:
            return self.memory_retriever.format_for_prompt(memories)
        except Exception:
            return ""

    def _trigger_distill(self, question: str, answer: str, sources: list[dict],
                         session_id: Optional[str], user_id: Optional[str],
                         injected_memories: list[dict]):
        """问答后 fire-and-forget 触发记忆蒸馏 + 兴趣图谱蒸馏，不阻塞返回。"""
        if not user_id:
            return

        # 记忆条目蒸馏（现有）
        if self.memory_distiller:
            try:
                asyncio.create_task(self.memory_distiller.distill_async(
                    question=question,
                    answer=answer,
                    sources=sources,
                    session_id=session_id,
                    user_id=user_id,
                    injected_memories=injected_memories,
                ))
            except RuntimeError:
                pass
            except Exception as e:
                print(f"⚠️ 记忆蒸馏触发失败: {e}")

        # 兴趣图谱蒸馏（新增）
        if self.interest_distiller:
            try:
                asyncio.create_task(self.interest_distiller.distill_async(
                    question=question,
                    answer=answer,
                    sources=sources,
                    session_id=session_id,
                    user_id=user_id,
                ))
            except RuntimeError:
                pass
            except Exception as e:
                print(f"⚠️ 兴趣图谱蒸馏触发失败: {e}")

    def _get_profile_context(self, user_id: Optional[str]) -> str:
        """
        读缓存画像注入 prompt（同步，无 LLM）。
        惰性触发：若需要刷新，fire-and-forget 异步重算，本次仍用旧缓存。
        未启用或失败返回空字符串。
        """
        if not self.profile_builder or not user_id:
            return ""
        try:
            # 惰性触发重算（不阻塞本次问答）
            if self.profile_builder.should_refresh(user_id):
                try:
                    asyncio.create_task(self.profile_builder.build_profile_async(user_id))
                except RuntimeError:
                    pass  # 无运行中的 event loop（同步测试环境）

            profile_text = self.profile_builder.get_cached_profile_text(user_id)
            if profile_text:
                return f"**用户研究画像：**\n{profile_text}\n"
            return ""
        except Exception:
            return ""

    def _get_interest_context(self, question: str, user_id: Optional[str]) -> str:
        """
        从用户兴趣图谱检索相关节点，序列化为上下文（同步，无 LLM）。
        未启用或失败返回空字符串。
        """
        if not self.interest_retriever or not user_id:
            return ""
        try:
            return self.interest_retriever.build_context(question, user_id)
        except Exception:
            return ""

    async def ask_with_session_stream(self, question: str, session_id: str, k: int = 5,
                                      paper_title: Optional[str] = None,
                                      paper_titles: Optional[list[str]] = None,
                                      user_id: Optional[str] = None):
        """
        流式版多轮对话 RAG 问答。

        Args:
            paper_title: 单篇论文过滤（来自 PDF 阅读器，向后兼容）
            paper_titles: 多篇论文过滤列表
            user_id: 当前用户 ID，用于数据隔离
        """
        from langchain_core.messages import HumanMessage

        effective_titles: Optional[list[str]] = None
        if paper_title:
            effective_titles = [paper_title]
        elif paper_titles:
            effective_titles = paper_titles

        session = self.session_store.get_session(session_id, user_id)
        if not session:
            yield {"type": "sources", "data": []}
            yield {"type": "done", "data": "📭 会话不存在，请创建新会话。"}
            return

        messages = self.session_store.get_messages(session_id)
        summary = session.get("summary", "")

        recent_for_rewrite = self.memory.format_for_rewrite(messages, max_turns=2)
        rewrite_result = self.query_rewriter.rewrite(question, recent_for_rewrite)
        rewritten_query = rewrite_result["query"]
        if not effective_titles:
            filter_hint = rewrite_result.get("filter_title")
            if filter_hint:
                effective_titles = [filter_hint]

        if self.hybrid_retriever:
            docs = self.hybrid_retriever.search(
                rewritten_query, k=k,
                filter_titles=effective_titles,
                user_id=user_id,
            )
        else:
            title_filter = (
                self.vector_store.build_title_filter(effective_titles, user_id=user_id)
                if effective_titles else ({"user_id": user_id} if user_id else None)
            )
            if title_filter:
                docs = self.vector_store.search_with_filter(
                    rewritten_query, k=k, filter_dict=title_filter
                )
            else:
                docs = self.vector_store.search(rewritten_query, k=k)

        sources = [
            {
                "title": doc.metadata.get("title", "未知"),
                "chunk_index": doc.metadata.get("chunk_index", -1),
                "content_preview": doc.page_content[:150] + "...",
            }
            for doc in docs
        ]
        yield {"type": "sources", "data": sources}

        if not docs:
            answer = "📭 知识库为空或未找到相关内容。请先上传论文。"
            self.session_store.add_message(session_id, "user", question)
            self.session_store.add_message(session_id, "assistant", answer, "[]")
            if len(messages) == 0:
                self.session_store.update_title(session_id, question[:40])
            yield {"type": "done", "data": answer}
            return

        chunks_text = self._format_context(docs)
        budget = self.memory.calculate_budget(chunks_text)
        chat_history = self.memory.format_for_prompt(messages, summary, budget["history_budget"])

        graph_context = ""
        if self.graph_retriever:
            try:
                graph_context = self.graph_retriever.retrieve(question, user_id=user_id)
            except Exception:
                graph_context = ""

        # 自生长记忆：检索相关记忆并注入（同步，无 LLM）
        injected_memories = self._retrieve_memories(question, user_id)
        memory_context = self._format_memory_context(injected_memories)
        # 用户画像：读缓存注入（同步，无 LLM）+ 惰性触发重算
        profile_context = self._get_profile_context(user_id)
        # 用户兴趣图谱：检索相关节点注入（同步，无 LLM）
        interest_context = self._get_interest_context(question, user_id)
        if interest_context:
            profile_context = (profile_context + "\n" + interest_context) if profile_context else interest_context

        if paper_title:
            paper_scope = (
                f"\n**当前阅读论文：** 用户正在阅读《{paper_title}》，请优先针对该论文回答，代词如'这个方法'、'该算法'均指该论文中的内容。\n"
            )
        elif effective_titles and len(effective_titles) > 0:
            titles_str = "、".join(f"《{t}》" for t in effective_titles)
            paper_scope = f"\n**检索范围限定：** 用户已将检索范围限定在以下论文：{titles_str}，请优先从这些论文中回答。\n"
        else:
            paper_scope = ""

        if chat_history:
            prompt_text = CONVERSATIONAL_RAG_PROMPT.format(
                chat_history=chat_history,
                graph_context=graph_context,
                memory_context=memory_context,
                profile_context=profile_context,
                context=chunks_text,
                question=question,
                paper_scope=paper_scope,
            )
        else:
            prompt_text = RAG_PROMPT_TEMPLATE.format(
                graph_context=graph_context,
                memory_context=memory_context,
                profile_context=profile_context,
                context=chunks_text,
                question=question,
                paper_scope=paper_scope,
            )

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

        self.session_store.add_message(session_id, "user", question)
        self.session_store.add_message(
            session_id, "assistant", full_answer, json.dumps(sources, ensure_ascii=False)
        )

        if len(messages) == 0:
            title = question[:40] + ("..." if len(question) > 40 else "")
            self.session_store.update_title(session_id, title)

        new_message_count = len(messages) + 2
        if self.memory.should_update_summary(new_message_count):
            all_messages = self.session_store.get_messages(session_id)
            new_summary = self.memory.generate_summary(all_messages)
            if new_summary:
                self.session_store.update_summary(session_id, new_summary)

        # 自生长记忆：问答后 fire-and-forget 蒸馏（不阻塞 SSE 连接关闭）
        self._trigger_distill(question, full_answer, sources, session_id, user_id, injected_memories)
