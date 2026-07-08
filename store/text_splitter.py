"""
文本切分模块
将论文长文本切成适合 embedding 的小块。
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    将长文本切分成小块。

    Args:
        text: 论文全文
        chunk_size: 每块最大字符数（默认 800）
        chunk_overlap: 相邻块重叠字符数（默认 100）

    Returns:
        切分后的文本块列表
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # 优先按段落分，其次按句子，最后按字符
        separators=["\n\n", "\n", ". ", "。", " ", ""],
        length_function=len,
    )

    chunks = splitter.split_text(text)
    return chunks
