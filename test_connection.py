"""
📚 论文管理 Agent - Step 1: 测试 LLM 连通性
运行方式: python test_connection.py

确保你已经：
1. 创建了 .env 文件（参考 .env.example）
2. 安装了依赖: pip install -r requirements.txt
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def check_env():
    """检查环境变量配置"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    print("=" * 50)
    print("🔍 环境变量检查")
    print("=" * 50)

    if not api_key:
        print("❌ OPENAI_API_KEY 未设置！")
        print("   请创建 .env 文件并填入你的 API Key")
        print("   参考 .env.example")
        return False

    # 隐藏显示 key（只显示前8位和后4位）
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"  ✅ API Key: {masked_key}")
    print(f"  ✅ Base URL: {base_url}")
    print(f"  ✅ Model: {model_name}")
    print()
    return True


def test_langchain_import():
    """测试 LangChain 导入"""
    print("=" * 50)
    print("📦 依赖库检查")
    print("=" * 50)

    try:
        import langchain
        print(f"  ✅ langchain: {langchain.__version__}")
    except ImportError:
        print("  ❌ langchain 未安装，运行: pip install -r requirements.txt")
        return False

    try:
        from langchain_openai import ChatOpenAI
        print("  ✅ langchain-openai: OK")
    except ImportError:
        print("  ❌ langchain-openai 未安装")
        return False

    try:
        from langchain_community.vectorstores import Chroma
        print("  ✅ langchain-community: OK")
    except ImportError:
        print("  ⚠️  langchain-community 未安装（第二步需要，暂时可跳过）")

    print()
    return True


def test_llm_connection():
    """测试 LLM 连通性"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    print("=" * 50)
    print("🤖 LLM 连通性测试")
    print("=" * 50)

    try:
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key,
            base_url=base_url,
        )

        # 发送一个简单的测试消息
        messages = [
            SystemMessage(content="你是一个学术助手，专门帮助研究生管理论文。"),
            HumanMessage(content="你好，请用一句话介绍你自己。"),
        ]

        print("  ⏳ 正在连接 LLM...")
        response = llm.invoke(messages)
        print(f"  ✅ 连接成功！")
        print(f"  🤖 模型回复: {response.content}")
        print()
        return True

    except Exception as e:
        print(f"  ❌ 连接失败: {str(e)}")
        print()
        print("  常见问题排查：")
        print("  1. API Key 是否正确？")
        print("  2. Base URL 是否正确？")
        print("  3. 网络是否能访问该 API？（国内可能需要代理）")
        print("  4. 模型名称是否正确？")
        return False


def test_simple_chain():
    """测试简单的 LangChain Chain"""
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")

    print("=" * 50)
    print("⛓️  LangChain Chain 测试")
    print("=" * 50)

    try:
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key,
            base_url=base_url,
        )

        # 构建一个简单的 prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个论文摘要助手。请用中文简洁地回答。"),
            ("human", "请用2-3句话解释什么是 {topic}"),
        ])

        # 构建 chain: prompt → LLM → 输出解析
        chain = prompt | llm | StrOutputParser()

        print("  ⏳ 测试 Chain (prompt → LLM → parser)...")
        result = chain.invoke({"topic": "对比学习 (Contrastive Learning)"})
        print(f"  ✅ Chain 运行成功！")
        print(f"  🤖 回答: {result}")
        print()
        return True

    except Exception as e:
        print(f"  ❌ Chain 运行失败: {str(e)}")
        return False


def main():
    print()
    print("🚀 论文管理 Agent - 环境与连通性测试")
    print("=" * 50)
    print()

    # Step 1: 检查环境变量
    if not check_env():
        sys.exit(1)

    # Step 2: 检查依赖
    if not test_langchain_import():
        sys.exit(1)

    # Step 3: 测试 LLM 连接
    if not test_llm_connection():
        sys.exit(1)

    # Step 4: 测试 Chain
    if not test_simple_chain():
        sys.exit(1)

    # 全部通过
    print("=" * 50)
    print("🎉 所有测试通过！环境准备就绪。")
    print("=" * 50)
    print()
    print("下一步：")
    print("  → 运行 python main.py 启动论文管理 Agent")
    print()


if __name__ == "__main__":
    main()
