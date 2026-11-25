import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  // 读取项目根目录唯一的 .env 文件
  const rootDir = path.resolve(__dirname, "..");
  const env = loadEnv(mode, rootDir, "");
  const fastapiTarget = `http://127.0.0.1:${env.FASTAPI_PORT || 8123}`;
  const gatewayTarget = `http://127.0.0.1:${env.GATEWAY_PORT || 4000}`;
  const apiPrefix = (env.API_PREFIX || "/api").replace(/\/$/, "");
  const copilotkitPath = `${apiPrefix}/copilotkit`;

  return {
    envDir: "../",
    envPrefix: ["VITE_", "COPILOTKIT_", "API_"],
    resolve: {
      alias: {
        "~": path.resolve(__dirname, "app"),
      },
    },
    plugins: [vue(), tailwindcss()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        // 1. 专职 UI 交互协议与智能体桥接流 (/api/copilotkit) 由 4000 端口 Node.js 运行时处理 (优先精确匹配)
        [copilotkitPath]: {
          target: gatewayTarget,
          changeOrigin: true,
        },
        // 2. 所有业务数据、文件上传与静态资源接口 (/api/...) 统一由 8123 端口 FastAPI 处理
        "/api": {
          target: fastapiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
