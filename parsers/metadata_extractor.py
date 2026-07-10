"""
论文元数据提取模块
使用 LLM 从论文第一页内容中提取标题、作者等信息。
比 pypdf 的启发式方法准确得多。
"""

import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


EXTRACT_PROMPT = """从以下论文的第一页内容中提取元数据。请返回 JSON 格式：

{
  "title": "论文完整标题（英文保持原文）",
  "authors": "所有作者姓名，用逗号分隔",
  "venue": "发表的期刊或会议名称（如 IEEE INFOCOM, NeurIPS, ACL 等，找不到填 null）",
  "abstract": "摘要内容（如果能找到的话，找不到就填 null）"
}

只返回 JSON，不要其他内容。

--- 论文第一页内容 ---
"""


class MetadataExtractor:
    """使用 LLM 提取论文元数据"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def extract(self, first_page_text: str) -> dict:
        """
        从论文第一页文本中提取标题、作者、摘要。

        Args:
            first_page_text: 论文第一页的文本内容

        Returns:
            {"title": str, "authors": str, "abstract": str | None}
        """
        # 只取前 2000 字符，避免 token 浪费
        text = first_page_text[:2000]

        messages = [
            SystemMessage(content="你是一个学术论文元数据提取助手。请从论文内容中精确提取标题和作者信息。"),
            HumanMessage(content=EXTRACT_PROMPT + text),
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()

            # 清理可能的 markdown 代码块标记
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)
            return {
                "title": result.get("title", "").strip() or None,
                "authors": result.get("authors", "").strip() or None,
                "venue": result.get("venue", "").strip() if result.get("venue") else None,
                "abstract": result.get("abstract", "").strip() if result.get("abstract") else None,
            }
        except (json.JSONDecodeError, Exception) as e:
            # LLM 提取失败，返回空
            return {"title": None, "authors": None, "abstract": None}
