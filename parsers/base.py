"""
解析器基类 - 定义统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    """论文解析结果"""

    # 提取的全文文本（Markdown 格式优先）
    text: str

    # 元数据
    title: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    total_pages: int = 0

    # 解析来源标记
    parser_backend: str = "unknown"

    # 按页面拆分的文本（可选，某些解析器支持）
    pages: list[str] = field(default_factory=list)


class PaperParser(ABC):
    """
    论文解析器抽象基类。

    所有解析器必须实现 parse() 方法，
    输入 PDF 路径，输出 ParseResult。
    """

    @abstractmethod
    def parse(self, pdf_path: str) -> ParseResult:
        """
        解析 PDF 文件。

        Args:
            pdf_path: PDF 文件的路径

        Returns:
            ParseResult: 包含提取文本和元数据的结果对象

        Raises:
            FileNotFoundError: PDF 文件不存在
            ValueError: PDF 文件无法解析
        """
        ...

    def get_name(self) -> str:
        """返回解析器名称"""
        return self.__class__.__name__
