# DeepAgent

基于 **FastAPI + LangGraph (`deepagents`) + CopilotKit AG-UI + Vue 3** 构建的多模态 AI 智能体应用，集成 **华为云 AgentArts**（代码沙箱、云浏览器、长期记忆）与 **PostgreSQL** 持久化存储。

---

## 核心特性

- **DeepAgent 智能体架构**：基于 `deepagents` 与 LangGraph 构建，内置状态持久化（`langgraph-checkpoint-postgres`）及多层中间件：
  - `SandboxLifecycleMiddleware`：按会话（`thread_id`）自动创建与管理沙箱生命周期。
  - `LongTermMemoryMiddleware`：对接 AgentArts 长期记忆服务，支持跨对话检索与记忆沉淀。
  - `MultimodalProcessorMiddleware`：支持多模态输入与上传文件的自动解析处理。
  - `CopilotKitMiddleware`：兼容 CopilotKit AG-UI 交互协议。
- **云端代码沙箱（Code Interpreter）**：通过 `AgentArtsBackend` 提供隔离的 Linux 工作区（默认 `/home/user`），支持 `read_file`、`write_file`、`edit_file`、`ls`、`glob`、`grep` 等文件操作。
- **云浏览器自动化（Browser Use）**：集成 `browser_use` 工具，通过本地桥接与 `agent-browser` CLI 连接远程 AgentArts 云浏览器（CDP），支持页面访问、元素快照、点击、表单填写、文本提取与截图。
- **文件上传与沙箱存储**：支持最大 20 MB 附件上传，文件直接写入对应会话沙箱的 `/home/user/uploads/` 目录，并提供下载/读取接口。
- **会话（Thread）管理**：基于 Tortoise ORM + PostgreSQL 存储会话元数据，支持按用户隔离（通过 `X-User-Id` 请求头鉴权）、创建、重命名、归档与历史消息查询。
- **独立前端界面**：`frontend/` 基于 Vue 3 + Vite + Tailwind CSS v4 + `@copilotkit/vue` 构建。

---

## 系统架构与端口说明

本项目采用前后端与协议网关分层架构：

| 服务组件 | 入口文件 | 默认端口 | 职责说明 |
| :--- | :--- | :--- | :--- |
| **FastAPI Agent 后端** | `main.py` (`app/main.py`) | `8123` (`FASTAPI_PORT`) | 提供 LangGraph AG-UI 端点（`/`）、健康检查、会话管理（`/api/threads`）与文件上传（`/api/upload`） |
| **CopilotKit UI Runtime** | `src/server.mjs` | `4000` (`GATEWAY_PORT`) | 专职处理 `/api/copilotkit*` UI 流式交互协议，并桥接至 FastAPI 后端 |
| **Vue 3 前端应用** | `frontend/` | `5173` | 开发环境通过 Vite 代理将 `/api/copilotkit` 转发至 `4000`，其余 `/api/*` 转发至 `8123` |
| **本地 AgentArts 转发代理** | `src/proxy.mjs` | `8000` (`PROXY_PORT`) | 可选：用于前后端分离联调远端 AgentArts 后端，解决 CORS 并自动注入鉴权头与 Session ID |
| **Caddy 统一网关（容器部署）** | `Caddyfile` | `8000` (`PORT`) | Docker 生产环境统一入口，将 `/api/copilotkit*` 路由至 `4000`，其余请求路由至 `8123` |

---

## 目录结构

```text
deepagent/
├── app/
│   ├── agent/          # 智能体定义 (agent.py)、工具集 (tools.py)、多模态处理 (multimodal.py)
│   ├── browser/        # AgentArts 云浏览器管理、本地桥接与 browser_use 工具
│   ├── memory/         # AgentArts 长期记忆客户端与中间件
│   ├── models/         # Tortoise ORM 数据模型 (Thread)
│   ├── routers/        # RESTful 路由 (/api/threads, /api/upload)
│   ├── sandbox/        # AgentArts 代码沙箱客户端、后端与生命周期中间件
│   ├── schemas/        # Pydantic 请求与响应模型
│   ├── config.py       # 全局配置读取
│   ├── database.py     # PostgreSQL / Tortoise ORM / Checkpointer 初始化
│   ├── dependencies.py # 通用依赖（X-User-Id 校验）
│   └── main.py         # FastAPI 应用工厂
├── src/
│   ├── server.mjs      # CopilotKit Node.js Runtime 服务 (端口 4000)
│   └── proxy.mjs       # 本地 AgentArts 请求转发代理 (端口 8000)
├── frontend/           # Vue 3 + Vite + @copilotkit/vue 前端工程
├── main.py             # 后端启动入口
├── langgraph.json      # LangGraph CLI 配置
├── pyproject.toml      # Python 依赖配置 (Python >= 3.13, uv 管理)
├── package.json        # Node.js 脚本与运行时依赖
├── Caddyfile           # 生产环境 Caddy 反向代理配置
├── Dockerfile          # 容器镜像构建文件
├── docker-entrypoint.sh# 容器启动脚本（同时拉起 FastAPI、Node Runtime、Caddy）
└── .env.example        # 环境变量配置模板
```

---

## 环境要求

- **Python** >= 3.13（推荐使用 [`uv`](https://docs.astral.sh/uv/) 管理虚拟环境与依赖）
- **Node.js** >= 22 LTS & npm
- **PostgreSQL** 数据库实例
- **华为云 AgentArts** 相关服务配置（代码沙箱、云浏览器、长期记忆及模型 API Key）

---

## 快速开始

### 1. 配置环境变量

复制环境变量模板并按实际情况填写：

```bash
cp .env.example .env
```

核心配置项说明（详见 [`.env.example`](.env.example)）：
- **服务与端口**：`API_PREFIX`（默认 `/api`）、`FASTAPI_PORT`（默认 `8123`）、`GATEWAY_PORT`（默认 `4000`）
- **PostgreSQL**：`POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`（或直接配置 `DATABASE_URL`）
- **大模型**：`MODEL_NAME`、`MODEL_PROVIDER`、`MODEL_BASE_URL`、`MODEL_API_KEY`
- **AgentArts 沙箱与浏览器**：`AGENTARTS_REGION`、`AGENTARTS_CODE_INTERPRETER_NAME`、`AGENTARTS_BROWSER_NAME`、`AGENTARTS_BROWSER_DATA_ENDPOINT` 等
- **AgentArts 长期记忆**：`AGENTARTS_MEMORY_SPACE_ID`、`AGENTARTS_MEMORY_API_KEY`、`AGENTARTS_MEMORY_TOP_K`
- **华为云 IAM 凭据**（如需 IAM 认证）：`HUAWEICLOUD_SDK_AK`、`HUAWEICLOUD_SDK_SK`

### 2. 安装依赖

```bash
# 安装 Python 依赖
uv sync

# 安装根目录 Node.js 依赖（CopilotKit Runtime、agent-browser 等）
npm install

# 安装前端依赖
npm --prefix frontend install
```

### 3. 启动开发环境

在项目根目录运行以下命令即可一键启动所有开发服务（日志输出至 `logs/` 目录）：

```bash
# 同时启动 FastAPI Agent (8123)、CopilotKit Runtime (4000)、代理与前端 (5173)
npm run dev
```

也可按需单独启动各组件：

```bash
# 仅启动后端（FastAPI Agent + CopilotKit Runtime）
npm run dev:backend

# 单独启动 FastAPI Agent
npm run dev:agent

# 单独启动 CopilotKit Runtime
npm run dev:runtime

# 单独启动前端及本地代理
npm run dev:frontend

# 单独启动本地 AgentArts 转发代理
npm run dev:proxy

# 清理 logs/ 下的日志文件
npm run clean:logs
```

启动后访问前端地址 `http://localhost:5173` 即可使用。

---

## Docker 部署

项目提供完整的容器化部署配置（`Dockerfile` + `docker-entrypoint.sh` + `Caddyfile`），容器内部会依次启动 FastAPI（`8123`）、Node.js CopilotKit Runtime（`4000`）与 Caddy 统一网关（默认暴露 `8000` 端口）。

```bash
# 构建镜像
docker build -t deepagent:latest .

# 运行容器（传入 .env 文件）
docker run -d --name deepagent -p 8000:8000 --env-file .env deepagent:latest
```

---

## 主要 API 接口

除健康检查与根路径 AG-UI 端点外，`/api/threads` 与 `/api/upload` 下的业务接口均要求在请求头中携带合法的 `X-User-Id`（仅允许字母、数字、下划线与短横线）。

| 方法与路径 | 说明 |
| :--- | :--- |
| `GET /ping` | 基础探活接口，返回 `{"status": "Healthy"}` |
| `GET /api/health` | 服务健康状态与版本信息（无需 `X-User-Id`） |
| `POST /api/copilotkit*` | CopilotKit UI 流式交互协议端点（由 `4000` 端口处理） |
| `GET /api/threads` | 获取当前用户的会话列表（支持 `agentId`、`includeArchived`、`limit`） |
| `POST /api/threads` | 创建新会话 |
| `PATCH /api/threads/{thread_id}` | 更新会话元数据 |
| `GET /api/threads/{thread_id}/messages` | 获取指定会话的历史消息 |
| `DELETE /api/threads/{thread_id}` | 删除会话并清理相关状态 |
| `POST /api/upload` | 上传文件至指定 `thread_id` 对应的沙箱 `/home/user/uploads/` |
| `GET /api/upload/file` | 从沙箱中读取或下载指定路径的文件 |
