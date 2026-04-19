# Qlunee Code

一个带前后端界面的 Agent 系统：

- 后端基于 FastAPI，复用 agent.py 的工具调用与多轮推理能力
- 前端基于 Vue 3 + Vite + Pinia，提供 ChatGPT 风格交互
- 支持任务管理、团队协作消息、异步队友结果回传

## 功能概览

- 聊天推理：前端输入，后端调用模型并返回回答
- 工具调用：bash/read_file/write_file/edit_file/TodoWrite 等
- 任务系统：创建、更新、查看任务
- 团队协作：spawn teammate、send_message、inbox 收发
- 异步结果展示：前端轮询 lead inbox，展示 coder 后续执行结果
- 会话持久化：前端 localStorage 保留历史会话

## 技术栈

- Backend: Python 3.13+, FastAPI, Uvicorn, Anthropic SDK
- Frontend: Vue 3, TypeScript, Vite, Pinia, Tailwind, Axios

## 目录结构

```text
.
├─ backend/
│  └─ agent/
│     ├─ agent.py          # 核心 agent 能力与工具处理
│     ├─ server.py         # FastAPI 服务入口
│     └─ tools.py          # 工具定义
├─ frontend/
│  ├─ src/
│  │  ├─ stores/chat.ts    # 会话状态、发送、停止、重试、inbox 轮询
│  │  ├─ services/api.ts   # HTTP API 封装
│  │  └─ services/stream.ts
│  └─ package.json
├─ .env.example
└─ pyproject.toml
```

## 环境要求

- macOS/Linux
- Python >= 3.13
- Node.js 22 LTS（推荐）

说明：Node 24 在本项目里可能出现依赖安装异常，建议固定 Node 22。

## 1. 后端准备与启动

### 1.1 安装 Python 依赖

```bash
cd /Users/liquan/Documents/Code/my_project/agent/Qlunee_code
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 1.2 配置环境变量

```bash
cp .env.example .env
```

至少需要在 .env 中配置：

```bash
ANTHROPIC_API_KEY=你的key
MODEL_ID=claude-sonnet-4-6
# 可选：兼容供应商网关
# ANTHROPIC_BASE_URL=https://api.anthropic.com

# 建议设置为项目根目录，保证工具可访问整个仓库
QLUNEE_WORKDIR=/Users/liquan/Documents/Code/my_project/agent/Qlunee_code
```

### 1.3 启动后端

```bash
cd /Users/liquan/Documents/Code/my_project/agent/Qlunee_code
source .venv/bin/activate
uvicorn backend.agent.server:app --host 127.0.0.1 --port 8000 --reload
```

启动后可访问：

- API 根信息: http://127.0.0.1:8000/
- Swagger 文档: http://127.0.0.1:8000/docs

## 2. 前端安装与启动

```bash
/opt/homebrew/opt/node@22/bin/npm --prefix /Users/liquan/Documents/Code/my_project/agent/Qlunee_code/frontend install
/opt/homebrew/opt/node@22/bin/npm --prefix /Users/liquan/Documents/Code/my_project/agent/Qlunee_code/frontend run dev
```

默认打开：

- http://127.0.0.1:5173/

可选前端环境变量（在 frontend/.env 中）：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_STREAM_MODE=http
VITE_API_TIMEOUT_MS=1200000
```

## 3. 前后端联调验证

### 3.1 健康检查

```bash
curl -s http://127.0.0.1:8000/api/health
```

### 3.2 发送聊天请求

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
	-H 'Content-Type: application/json' \
	-d '{"conversationId":"demo","message":"你好，请列出当前项目根目录文件"}'
```

### 3.3 查看异步队友消息

```bash
curl -s http://127.0.0.1:8000/api/inbox/lead
```

说明：该接口是“读取并清空”lead 收件箱，前端会定时轮询并把消息追加到聊天中。

## 4. 当前后端 API

- GET /api/health: 服务状态、workdir、任务数、inbox 文件数
- POST /api/chat: 主聊天接口
- GET /api/tasks: 任务列表
- POST /api/tasks: 创建任务
- PATCH /api/tasks/{task_id}: 更新任务状态/依赖/owner
- GET /api/inbox/lead: 读取 lead 收件箱（drain）

## 5. 常见问题

### 1) 前端显示超时

- 检查 frontend 的 VITE_API_TIMEOUT_MS 是否足够大
- 长链路任务（spawn teammate + 工具调用）耗时会明显增加

### 2) 后端日志显示 coder 已完成，但前端没看到

- 确认后端包含 GET /api/inbox/lead 接口
- 确认前端已重启（让轮询逻辑生效）
- 注意 inbox 为 drain 语义：被读取后会清空

### 3) uvicorn 启动报模块导入错误

- 在项目根目录启动
- 确认已激活 .venv
- 确认已安装依赖：pip install -e .

### 4) npm install 异常

- 建议使用 Node 22 LTS
- 按本文命令使用固定 npm 路径执行

## 6. 开发建议

- 前端改动后可执行：npm --prefix frontend run build
- 后端改动后可先用 /docs 快速验证请求结构
- 若要提高异步可见性，可增加前端轮询状态展示与消息来源过滤
