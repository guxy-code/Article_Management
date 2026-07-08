"""
知识图谱三元组提取模块
使用 LLM 从论文内容中提取结构化知识。
"""

import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()


EXTRACTION_PROMPT = """你是一个学术论文知识图谱提取专家。请从以下论文内容中提取结构化知识。

**提取规则：**
1. methods：论文提出的核心方法/算法（通常 1-3 个）
2. problems：论文要解决的研究问题/动机（通常 1-2 个）
3. concepts：论文使用的核心技术概念（通常 3-6 个关键术语）
4. datasets：论文实验使用的数据集
5. relations：方法之间的关系
   - IMPROVES：新方法改进了旧方法
   - SOLVES：方法解决了问题
   - USES：方法使用了某技术

**输出要求：**
- 只输出 JSON，不要其他文字
- 名称用英文（保持论文原文术语）
- description 用中文简要描述

**JSON 格式：**
{
  "methods": [{"name": "方法英文名", "description": "中文描述"}],
  "problems": [{"name": "问题英文名", "description": "中文描述"}],
  "concepts": ["concept1", "concept2"],
  "datasets": ["dataset1", "dataset2"],
  "relations": [
    {"type": "IMPROVES", "from": "新方法名", "to": "旧方法名"},
    {"type": "SOLVES", "from": "方法名", "to": "问题名"},
    {"type": "USES", "from": "方法名", "to": "技术名"}
  ]
}

--- 论文内容 ---
"""


class KnowledgeExtractor:
    """使用 LLM 从论文中提取知识图谱三元组"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "deepseek-v4-flash"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def extract(self, text: str, title: str = "", authors: str = "") -> dict:
        """
        从论文文本中提取知识图谱数据。

        Args:
            text: 论文文本（建议用摘要+前几页，控制 token）
            title: 论文标题
            authors: 作者

        Returns:
            结构化的图谱数据 dict
        """
        # 控制输入长度（只取前 3000 字符，通常涵盖摘要和方法概述）
        input_text = text[:3000]

        if title:
            input_text = f"Title: {title}\nAuthors: {authors}\n\n{input_text}"

        messages = [
            SystemMessage(content="你是学术论文知识图谱提取专家。请严格按要求输出 JSON。"),
            HumanMessage(content=EXTRACTION_PROMPT + input_text),
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()

            # 清理 markdown 代码块
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            # 附加论文元数据
            result["title"] = title
            result["authors"] = authors

            return result

        except json.JSONDecodeError:
            # LLM 输出格式不对，返回最基本的结构
            return {
                "title": title,
                "authors": authors,
                "methods": [],
                "problems": [],
                "concepts": [],
                "datasets": [],
                "relations": [],
            }
        except Exception as e:
            print(f"⚠️ 知识提取失败: {e}")
            return {
                "title": title,
                "authors": authors,
                "methods": [],
                "problems": [],
                "concepts": [],
                "datasets": [],
                "relations": [],
            }
