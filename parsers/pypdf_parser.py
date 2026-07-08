"""
PyPDF 解析器 - 轻量级实现
优点：零依赖、速度快
缺点：双栏论文会乱序、公式/表格解析差
"""

import os
from pypdf import PdfReader

from parsers.base import PaperParser, ParseResult


class PyPDFParser(PaperParser):
    """使用 pypdf 库解析 PDF"""

    def parse(self, pdf_path: str) -> ParseResult:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        try:
            reader = PdfReader(pdf_path)
        except Exception as e:
            raise ValueError(f"无法解析 PDF 文件: {e}")

        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        if not pages_text:
            raise ValueError(f"PDF 文件中未提取到任何文本: {pdf_path}")

        full_text = "\n\n".join(pages_text)

        # 尝试从第一页提取标题和作者（简单启发式）
        title = self._extract_title(pages_text[0]) if pages_text else None
        abstract = self._extract_abstract(full_text)

        return ParseResult(
            text=full_text,
            title=title,
            abstract=abstract,
            total_pages=len(reader.pages),
            parser_backend="pypdf",
            pages=pages_text,
        )

    def _extract_title(self, first_page: str) -> str | None:
        """
        简单启发式提取标题：取第一页前几行中最长的那行。
        （学术论文标题通常是第一页最显眼的文字）
        """
        lines = [l.strip() for l in first_page.split("\n") if l.strip()]
        if not lines:
            return None

        # 取前5行中最长的作为标题（粗略方法）
        candidates = lines[:5]
        title = max(candidates, key=len)

        # 标题不应太短或太长
        if len(title) < 5 or len(title) > 200:
            return None
        return title

    def _extract_abstract(self, text: str) -> str | None:
        """尝试提取摘要（找 Abstract 关键字后的段落）"""
        text_lower = text.lower()

        # 查找 "abstract" 关键字
        idx = text_lower.find("abstract")
        if idx == -1:
            return None

        # 从 abstract 之后开始提取
        after_abstract = text[idx + len("abstract"):].strip()

        # 去掉可能的分隔符
        if after_abstract.startswith((":", ".", "—", "-")):
            after_abstract = after_abstract[1:].strip()

        # 取前 1500 字符作为摘要范围，找第一个段落结束
        chunk = after_abstract[:1500]

        # 找到 "introduction" 或 "keywords" 作为摘要结束标记
        for end_marker in ["introduction", "keywords", "1.", "1 "]:
            end_idx = chunk.lower().find(end_marker)
            if end_idx > 50:  # 摘要至少要有 50 字符
                return chunk[:end_idx].strip()

        # 如果没找到结束标记，取前 500 字符
        return chunk[:500].strip() if len(chunk) > 50 else None
