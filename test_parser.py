"""
测试解析器模块
用法：python test_parser.py <pdf文件路径>
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import get_parser


def test_parser(pdf_path: str, backend: str = "pypdf"):
    """测试解析器"""
    print(f"\n{'=' * 50}")
    print(f"📄 测试 PDF 解析器")
    print(f"{'=' * 50}")
    print(f"  文件: {pdf_path}")
    print(f"  后端: {backend}")
    print()

    # 获取解析器
    parser = get_parser(backend)
    print(f"  ✅ 解析器: {parser.get_name()}")

    # 解析
    print(f"  ⏳ 正在解析...")
    result = parser.parse(pdf_path)

    print(f"  ✅ 解析完成！")
    print(f"\n{'=' * 50}")
    print(f"📊 解析结果")
    print(f"{'=' * 50}")
    print(f"  标题: {result.title or '未识别'}")
    print(f"  作者: {result.authors or '未识别'}")
    print(f"  总页数: {result.total_pages}")
    print(f"  文本长度: {len(result.text)} 字符")
    print(f"  解析后端: {result.parser_backend}")

    if result.abstract:
        print(f"\n📝 摘要:")
        print(f"  {result.abstract[:300]}...")

    print(f"\n📖 正文前 500 字符:")
    print(f"  {result.text[:500]}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_parser.py <pdf文件路径> [backend]")
        print("  backend: pypdf (默认) 或 mineru")
        print()
        print("示例:")
        print("  python test_parser.py papers/attention.pdf")
        print("  python test_parser.py papers/attention.pdf mineru")
        sys.exit(1)

    pdf_path = sys.argv[1]
    backend = sys.argv[2] if len(sys.argv) > 2 else "pypdf"

    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    try:
        test_parser(pdf_path, backend)
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        sys.exit(1)
