"""
BM25 关键词检索索引
支持中英混合学术文本的精确术语匹配。
"""

import re
from typing import Optional

import jieba
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document


# 英文连续串正则（保留整词：FedAvg, Non-IID, SCAFFOLD 等）
ENGLISH_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9\-_\.]*[A-Za-z0-9]|[A-Za-z]")
# 中文字符
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def tokenize_academic(text: str) -> list[str]:
    """
    学术文本分词：保留英文连续串整词，中文用 jieba 分词。

    策略：
    1. 用正则将文本拆分为英文块和中文块
    2. 英文块：保留整词（FedAvg, Non-IID 不会被拆开）
    3. 中文块：jieba 分词
    4. 过滤掉长度 < 2 的中文词和停用词
    """
    tokens = []
    # 找出所有英文串的位置
    english_spans = [(m.start(), m.end(), m.group().lower()) for m in ENGLISH_PATTERN.finditer(text)]

    # 标记哪些位置已被英文覆盖
    covered = set()
    for start, end, token in english_spans:
        if len(token) >= 2:  # 只保留长度>=2的英文词
            tokens.append(token)
        for i in range(start, end):
            covered.add(i)

    # 提取未被英文覆盖的中文部分
    chinese_parts = []
    current = []
    for i, char in enumerate(text):
        if i not in covered and CHINESE_PATTERN.match(char):
            current.append(char)
        else:
            if current:
                chinese_parts.append("".join(current))
                current = []
    if current:
        chinese_parts.append("".join(current))

    # 对中文部分做 jieba 分词
    for part in chinese_parts:
        words = jieba.lcut(part)
        for w in words:
            w = w.strip()
            if len(w) >= 2:  # 过滤单字
                tokens.append(w)

    return tokens


class BM25Store:
    """BM25 关键词检索索引（内存中）"""

    def __init__(self):
        self.documents: list[Document] = []
        self.tokenized_corpus: list[list[str]] = []
        self.index: Optional[BM25Okapi] = None

    def build_index(self, documents: list[Document]):
        """从文档列表构建 BM25 索引"""
        self.documents = list(documents)
        self.tokenized_corpus = [tokenize_academic(doc.page_content) for doc in self.documents]

        if self.tokenized_corpus:
            self.index = BM25Okapi(self.tokenized_corpus)

    def add_documents(self, documents: list[Document]):
        """增量添加文档并重建索引"""
        self.documents.extend(documents)
        new_tokens = [tokenize_academic(doc.page_content) for doc in documents]
        self.tokenized_corpus.extend(new_tokens)

        if self.tokenized_corpus:
            self.index = BM25Okapi(self.tokenized_corpus)

    def remove_by_title(self, title: str):
        """删除某篇论文的所有 chunk 并重建索引"""
        filtered = [(doc, tokens) for doc, tokens in zip(self.documents, self.tokenized_corpus)
                    if doc.metadata.get("title") != title]

        if filtered:
            self.documents, self.tokenized_corpus = zip(*filtered)
            self.documents = list(self.documents)
            self.tokenized_corpus = list(self.tokenized_corpus)
        else:
            self.documents = []
            self.tokenized_corpus = []

        if self.tokenized_corpus:
            self.index = BM25Okapi(self.tokenized_corpus)
        else:
            self.index = None

    def search(self, query: str, k: int = 20) -> list[tuple[Document, float]]:
        """
        BM25 检索，返回 (Document, score) 列表，按分数降序。

        Args:
            query: 检索查询
            k: 返回结果数量

        Returns:
            [(Document, bm25_score), ...]
        """
        if not self.index or not self.documents:
            return []

        query_tokens = tokenize_academic(query)
        if not query_tokens:
            return []

        scores = self.index.get_scores(query_tokens)

        # 取 top-k
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有分数的
                results.append((self.documents[idx], float(scores[idx])))

        return results

    @property
    def total_documents(self) -> int:
        return len(self.documents)
