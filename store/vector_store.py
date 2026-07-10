"""
向量存储模块 - 基于 Chroma
负责论文 chunk 的 embedding、存储、检索。
"""

import os
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


# 向量库持久化目录
PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")


class VectorStore:
    """向量数据库封装，支持论文入库和检索"""

    def __init__(
        self,
        persist_dir: str = PERSIST_DIR,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.persist_dir = persist_dir

        # 从环境变量读取配置
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY"))
        self.base_url = base_url or os.getenv("EMBEDDING_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        self.embedding_model = embedding_model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

        # 初始化 embedding 函数
        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model,
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # 加载或创建向量库
        self._vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name="papers",
        )

    def add_paper(
        self,
        chunks: list[str],
        title: str,
        authors: str = "unknown",
        source_path: str = "",
        user_id: str = "system",
    ) -> int:
        """
        将论文的 chunk 列表存入向量库。

        Args:
            chunks: 切分后的文本块列表
            title: 论文标题
            authors: 作者
            source_path: PDF 文件路径
            user_id: 所属用户 ID

        Returns:
            存入的 chunk 数量
        """
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "title": title,
                    "authors": authors,
                    "source": source_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "user_id": user_id,
                },
            )
            documents.append(doc)

        self._vectorstore.add_documents(documents)
        return len(documents)

    def search(self, query: str, k: int = 5, user_id: Optional[str] = None) -> list[Document]:
        """
        语义检索：根据查询找到最相关的 chunk。

        Args:
            query: 自然语言查询
            k: 返回结果数量
            user_id: 如果提供，只检索该用户的文档

        Returns:
            最相关的 Document 列表（包含内容和元数据）
        """
        if user_id:
            return self._vectorstore.similarity_search(
                query, k=k, filter={"user_id": user_id}
            )
        return self._vectorstore.similarity_search(query, k=k)

    def search_with_score(self, query: str, k: int = 5) -> list[tuple[Document, float]]:
        """
        带相似度分数的检索。

        Returns:
            [(Document, score), ...] 分数越小越相似
        """
        results = self._vectorstore.similarity_search_with_score(query, k=k)
        return results

    def list_papers(self, user_id: Optional[str] = None) -> list[str]:
        """列出已入库论文的标题，可按用户过滤"""
        if user_id:
            data = self._vectorstore.get(where={"user_id": user_id})
        else:
            data = self._vectorstore.get()
        titles = set()
        for meta in data.get("metadatas", []):
            if meta and "title" in meta:
                titles.add(meta["title"])
        return sorted(titles)

    def get_paper_chunks(self, title: str, user_id: Optional[str] = None) -> list[Document]:
        """获取某篇论文的所有 chunk，可按用户过滤"""
        if user_id:
            results = self._vectorstore.get(
                where={"$and": [{"user_id": user_id}, {"title": title}]}
            )
        else:
            results = self._vectorstore.get(where={"title": title})
        documents = []
        for i, content in enumerate(results.get("documents", [])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            documents.append(Document(page_content=content, metadata=meta))
        return documents

    def has_paper(self, title: str, user_id: Optional[str] = None) -> bool:
        """检查某篇论文是否已入库，可按用户过滤"""
        if user_id:
            results = self._vectorstore.get(
                where={"$and": [{"user_id": user_id}, {"title": title}]}
            )
        else:
            results = self._vectorstore.get(where={"title": title})
        return len(results.get("ids", [])) > 0

    def delete_paper(self, title: str, user_id: Optional[str] = None) -> bool:
        """删除某篇论文的所有 chunk，可按用户过滤"""
        if user_id:
            results = self._vectorstore.get(
                where={"$and": [{"user_id": user_id}, {"title": title}]}
            )
        else:
            results = self._vectorstore.get(where={"title": title})
        ids = results.get("ids", [])
        if ids:
            self._vectorstore.delete(ids=ids)
            return True
        return False

    def search_with_filter(self, query: str, k: int = 5, filter_dict: dict = None, user_id: Optional[str] = None) -> list[Document]:
        """
        带 metadata 过滤的语义检索。

        Args:
            query: 自然语言查询
            k: 返回结果数量
            filter_dict: Chroma filter，如 {"title": "某论文标题"}
                         或多篇: {"title": {"$in": ["A", "B"]}}
            user_id: 如果提供，自动与 filter_dict 组合 $and 过滤

        Returns:
            过滤后的最相关 Document 列表
        """
        combined_filter = self._merge_filter(filter_dict, user_id)
        if combined_filter:
            return self._vectorstore.similarity_search(query, k=k, filter=combined_filter)
        return self._vectorstore.similarity_search(query, k=k)

    def build_title_filter(self, titles: list[str], user_id: Optional[str] = None) -> Optional[dict]:
        """
        从论文标题列表构建 Chroma filter，可附加 user_id 条件。

        单篇: {"title": "xxx"} 或附加 user_id 后 $and 版本
        多篇: {"title": {"$in": [...]}} 或附加 user_id 后 $and 版本
        空:   None（不过滤）或只有 user_id 过滤
        """
        if not titles:
            return {"user_id": user_id} if user_id else None

        if len(titles) == 1:
            title_filter = {"title": titles[0]}
        else:
            title_filter = {"title": {"$in": titles}}

        return self._merge_filter(title_filter, user_id)

    def _merge_filter(self, filter_dict: Optional[dict], user_id: Optional[str]) -> Optional[dict]:
        """将 filter_dict 和 user_id 合并为 Chroma $and 过滤器"""
        if filter_dict and user_id:
            return {"$and": [{"user_id": user_id}, filter_dict]}
        if filter_dict:
            return filter_dict
        if user_id:
            return {"user_id": user_id}
        return None

    def get_all_documents(self, user_id: Optional[str] = None) -> list[Document]:
        """获取向量库中所有文档（用于构建 BM25 索引），可按用户过滤"""
        if user_id:
            data = self._vectorstore.get(where={"user_id": user_id})
        else:
            data = self._vectorstore.get()
        documents = []
        contents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        for i, content in enumerate(contents):
            meta = metadatas[i] if i < len(metadatas) else {}
            documents.append(Document(page_content=content, metadata=meta or {}))

        return documents

    @property
    def total_chunks(self) -> int:
        """向量库中的总 chunk 数"""
        return self._vectorstore._collection.count()
