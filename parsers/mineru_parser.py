"""
MinerU 解析器 - 高质量实现
优点：双栏识别、公式转 LaTeX、表格结构化、输出 Markdown
缺点：需要 GPU (8GB+ VRAM)、安装较重、速度较慢

安装方法：
    pip install magic-pdf
    详见: https://github.com/opendatalab/MinerU
"""

import os
import tempfile

from parsers.base import PaperParser, ParseResult

try:
    from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
    from magic_pdf.pipe.UNIPipe import UNIPipe
    from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter

    MINERU_AVAILABLE = True
except ImportError:
    MINERU_AVAILABLE = False


class MinerUParser(PaperParser):
    """使用 MinerU (magic-pdf) 解析 PDF，输出结构化 Markdown"""

    def __init__(self):
        if not MINERU_AVAILABLE:
            raise ImportError(
                "MinerU 未安装。请运行:\n"
                "  pip install magic-pdf\n"
                "详见: https://github.com/opendatalab/MinerU"
            )

    def parse(self, pdf_path: str) -> ParseResult:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        try:
            # 读取 PDF 二进制内容
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            # 创建临时输出目录
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 使用 MinerU 的 UNIPipe 进行解析
                image_writer = FileBasedDataWriter(os.path.join(tmp_dir, "images"))
                reader = FileBasedDataReader("")

                # 执行解析
                pipe = UNIPipe(pdf_bytes, {"_pdf_type": "", "model_list": []}, image_writer)
                pipe.pipe_classify()
                pipe.pipe_analyze()
                pipe.pipe_parse()

                # 获取 Markdown 输出
                md_content = pipe.pipe_mk_markdown(
                    os.path.join(tmp_dir, "images"),
                    drop_mode="none"
                )

        except ImportError:
            raise ImportError("MinerU 依赖未完整安装，请检查 magic-pdf 包。")
        except Exception as e:
            raise ValueError(f"MinerU 解析失败: {e}")

        if not md_content or not md_content.strip():
            raise ValueError(f"MinerU 未能从 PDF 中提取内容: {pdf_path}")

        # 从 Markdown 中提取元数据
        title = self._extract_title_from_md(md_content)
        abstract = self._extract_abstract_from_md(md_content)

        return ParseResult(
            text=md_content,
            title=title,
            abstract=abstract,
            total_pages=0,  # MinerU 输出不按页分
            parser_backend="mineru",
            pages=[],
        )

    def _extract_title_from_md(self, md: str) -> str | None:
        """从 Markdown 中提取标题（通常是第一个 # 标题）"""
        for line in md.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        # 如果没有 # 标题，取第一行非空文本
        for line in md.split("\n"):
            line = line.strip()
            if line and not line.startswith(("!", "[", "---")):
                return line[:200]
        return None

    def _extract_abstract_from_md(self, md: str) -> str | None:
        """从 Markdown 中提取摘要"""
        md_lower = md.lower()
        idx = md_lower.find("abstract")
        if idx == -1:
            return None

        after = md[idx + len("abstract"):].strip()
        if after.startswith((":", ".", "—", "-", "\n")):
            after = after[1:].strip()

        # 找到下一个标题作为结束
        lines = after.split("\n")
        abstract_lines = []
        for line in lines:
            if line.strip().startswith("#") or line.strip().lower().startswith(
                ("introduction", "1.", "keywords")
            ):
                break
            abstract_lines.append(line)

        abstract = "\n".join(abstract_lines).strip()
        return abstract[:1000] if len(abstract) > 50 else None
