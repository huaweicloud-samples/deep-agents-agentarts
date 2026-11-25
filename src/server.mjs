/**
 * CopilotKit UI Runtime Server.
 * 端口 4000 服务专职：仅负责 CopilotKit UI 交互协议与智能体桥接转换，
 * 业务数据接口（Threads、Upload、静态资源等）不经过此服务，直接由后端 FastAPI 处理。
 */
import { createServer } from "node:http";
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";

// 读取根目录统一的 .env 文件
try {
  process.loadEnvFile();
} catch (_) {}

const fastapiPort = process.env.FASTAPI_PORT || "8123";
const agentUrl = process.env.LANGGRAPH_DEPLOYMENT_URL || `http://127.0.0.1:${fastapiPort}`;
const apiPrefix = (process.env.API_PREFIX || "/api").replace(/\/$/, "");
const basePath = `${apiPrefix}/copilotkit`;

// 1. 初始化 CopilotRuntime 智能体网桥（仅负责 UI 交互协议转换）
const runtime = new CopilotRuntime({
  agents: {
    sample_agent: new HttpAgent({ url: agentUrl }),
  },
});

const copilotListener = createCopilotNodeListener({
  runtime,
  basePath: basePath,
  cors: true,
});

// 2. 仅处理 UI 协议请求，不处理或透传任何其他业务接口
const server = createServer((req, res) => {
  copilotListener(req, res);
});

const PORT = process.env.GATEWAY_PORT || 4000;
server.listen(PORT, "0.0.0.0", () => {
  console.log(`CopilotKit UI Runtime running on http://0.0.0.0:${PORT} (basePath: ${basePath}) -> ${agentUrl}`);
});
