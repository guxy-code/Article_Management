"""
PDF 解析模块 - 分层架构
支持 pypdf 和 MinerU 两种后端，通过配置切换。
"""

from parsers.base import PaperParser, ParseResult
from parsers.pypdf_parser import PyPDFParser

# MinerU 是可选依赖，没装也不影响使用 pypdf
try:
    from parsers.mineru_parser import MinerUParser
except ImportError:
    MinerUParser = None


def get_parser(backend: str = "pypdf") -> PaperParser:
    """
    工厂函数：根据配置获取解析器实例。

    Args:
        backend: "pypdf" 或 "mineru"

    Returns:
        PaperParser 实例
    """
    if backend == "pypdf":
        return PyPDFParser()
    elif backend == "mineru":
        if MinerUParser is None:
            raise ImportError(
                "MinerU 未安装。请运行: pip install magic-pdf\n"
                "详见: https://github.com/opendatalab/MinerU"
            )
        return MinerUParser()
    else:
        raise ValueError(f"不支持的解析后端: {backend}，可选: pypdf, mineru")
