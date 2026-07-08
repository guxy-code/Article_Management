"""
📚 论文管理 Agent - 主程序
命令行对话交互，支持上传论文、语义检索、智能问答。

用法：python main.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from store.vector_store import VectorStore
from rag.qa_chain import PaperQAChain
from tools import add_paper, ask_paper, search_papers, list_papers, delete_paper, init_tools


SYSTEM_PROMPT = """你是一个专业的学术论文管理助手，帮助研究生管理和理解他们的论文库。

你的能力：
1. 上传论文（add_paper）：用户提供 PDF 路径，你帮他解析并存入知识库
2. 论文问答（ask_paper）：基于已入库的论文内容回答学术问题
3. 语义检索（search_papers）：在论文库中搜索相关内容片段
4. 列出论文（list_papers）：展示知识库中有哪些论文
5. 删除论文（delete_paper）：从知识库中移除某篇论文

使用规则：
- 用户问学术问题时，用 ask_paper 工具
- 用户想看原文片段时，用 search_papers 工具
- 用户说"上传"、"添加"、提供 PDF 路径时，用 add_paper 工具
- 回答要简洁、准确、用中文
- 如果知识库为空，提醒用户先上传论文"""


def create_agent():
    """创建论文管理 Agent"""

    # 初始化向量库和问答链
    vector_store = VectorStore()
    qa_chain = PaperQAChain(vector_store=vector_store)

    # 注入全局依赖给 tools
    init_tools(vector_store, qa_chain)

    # LLM
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME", "deepseek-v4-flash"),
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    # 工具列表
    tools = [add_paper, ask_paper, search_papers, list_papers, delete_paper]

    # 创建 ReAct Agent
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    return agent


def main():
    print()
    print("=" * 60)
    print("📚 论文管理 Agent 已启动！")
    print("=" * 60)
    print()
    print("支持功能：")
    print("  • 上传论文：提供 PDF 路径即可入库")
    print("  • 论文问答：问任何关于已入库论文的问题")
    print("  • 语义检索：搜索论文中的相关内容")
    print("  • 论文管理：列出、删除已有论文")
    print()
    print("输入 'exit' 或 '退出' 结束对话")
    print("=" * 60)

    agent = create_agent()
    chat_history = []

    while True:
        try:
            user_input = input("\n👤 你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q", "退出"]:
            print("👋 再见！祝科研顺利！")
            break

        try:
            # 构建消息列表
            messages = chat_history + [HumanMessage(content=user_input)]

            # 调用 Agent
            result = agent.invoke({"messages": messages})

            # 提取最终回复
            output_messages = result["messages"]
            # 找最后一条 AI 消息
            final_response = ""
            for msg in reversed(output_messages):
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    final_response = msg.content
                    break

            if not final_response:
                # 如果没找到纯文本回复，取最后一条消息
                final_response = output_messages[-1].content if output_messages else "没有回复"

            print(f"\n🤖 Agent: {final_response}")

            # 更新对话历史（保留最近 10 轮）
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=final_response))
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]

        except Exception as e:
            print(f"\n❌ 出错了: {str(e)}")
            print("  请重试，或输入 'exit' 退出。")


if __name__ == "__main__":
    main()
