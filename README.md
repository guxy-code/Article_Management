# 📚 论文管理 Agent

研究生论文阅读管理系统，基于 LangChain + 向量数据库 + 图数据库。

## 功能规划

- **第一期**：上传 PDF → 向量存储 → 语义检索问答
- **第二期**：加入 Neo4j 图数据库，管理论文引用/方法/作者关系
- **第三期**：记忆 + 主动推荐

## 快速开始

### 1. 安装依赖

```bash
cd paper-agent
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 测试连通性

```bash
python test_connection.py
```

### 4. 启动 Agent（第一期完成后）

```bash
python main.py
```

## 支持的 LLM

本项目使用 OpenAI 兼容接口，支持：

| 模型 | BASE_URL | 说明 |
|------|----------|------|
| OpenAI GPT-4o-mini | `https://api.openai.com/v1` | 默认 |
| DeepSeek | `https://api.deepseek.com/v1` | 国内直连 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云 |
| 本地 Ollama | `http://localhost:11434/v1` | 免费本地 |

只需修改 `.env` 中的 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY` 即可切换。
