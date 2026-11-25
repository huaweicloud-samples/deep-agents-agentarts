/**
 * 本地 AgentArts 请求转发代理服务
 * 
 * 专用于前后端分离场景下，通过服务端 HTTP 请求代理 AgentArts 远端后端，
 * 彻底绕过浏览器的同源安全策略（CORS 限制），同时在服务端统一注入鉴权 Token 与 Session ID。
 */
import { createServer } from "node:http";
import http from "node:http";
import https from "node:https";
import { URL, fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

// 1. 读取根目录统一的 .env 配置文件 (使用绝对路径，避免工作目录变化导致漏读)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const envPath = path.join(rootDir, ".env");
if (fs.existsSync(envPath)) {
  try {
    process.loadEnvFile(envPath);
  } catch (err) {
    console.warn(`[Proxy Warning] 加载 .env 异常: ${err.message}`);
  }
}

const TARGET_URL = (process.env.AGENTARTS_BACKEND_URL || "http://127.0.0.1:8123").replace(/\/$/, "");
const AUTH_TOKEN = process.env.AGENTARTS_AUTH_TOKEN || "";
const SESSION_ID = process.env.AGENTARTS_SESSION_ID || "";
const PORT = Number.parseInt(process.env.PROXY_PORT || "8000", 10);

const targetBase = new URL(TARGET_URL);
const targetBasePath = targetBase.pathname.replace(/\/$/, "");

console.log("==================================================");
console.log("  AgentArts 本地请求转发代理已配置");
console.log(`  转发目标 Host:       ${targetBase.host}`);
console.log(`  远端 Base Path:      ${targetBasePath || "/"}`);
console.log(`  注入 Session-Id:     ${SESSION_ID ? "已配置" : "未配置"}`);
console.log(`  注入 Authorization:  ${AUTH_TOKEN ? "已配置" : "未配置"}`);
console.log(`  本地监听端口:        ${PORT}`);
console.log("==================================================");

function setCorsHeaders(res, origin) {
  const allowedOrigin = origin || "*";
  res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-User-Id, X-Hw-Agentarts-Session-Id, *");
  res.setHeader("Access-Control-Max-Age", "86400");
}

let requestSeq = 0;

const server = createServer((req, res) => {
  const reqId = ++requestSeq;
  const startTime = Date.now();
  const origin = req.headers.origin;
  const clientIp = req.socket.remoteAddress || req.headers["x-forwarded-for"] || "-";

  // 1. OPTIONS 跨域预检快速响应（直接返回 204，消除浏览器跨域拦截）
  if (req.method === "OPTIONS") {
    setCorsHeaders(res, origin);
    res.writeHead(204);
    res.end();
    console.log(`[Proxy] [#${reqId}] ${clientIp} - OPTIONS ${req.url} -> 204 No Content (Preflight) (${Date.now() - startTime}ms)`);
    return;
  }

  // 2. 构造远端完整路径 (关键：保留远端 TARGET_URL 中的 basePath，避免被 req.url 覆盖)
  const reqUrl = req.url || "/";
  const proxyPath = `${targetBasePath}${reqUrl.startsWith("/") ? reqUrl : `/${reqUrl}`}`;

  const isHttps = targetBase.protocol === "https:";
  const client = isHttps ? https : http;

  // 3. 构造转发请求头
  const proxyHeaders = { ...req.headers };
  // 重写 Host 为远端域名
  proxyHeaders.host = targetBase.host;
  // 移除浏览器特有的 origin 和 referer，防止远端网关触发不必要的跨域策略拦截
  delete proxyHeaders.origin;
  delete proxyHeaders.referer;

  // 自动注入平台 Session ID 与鉴权 Token
  if (SESSION_ID) {
    proxyHeaders["x-hw-agentarts-session-id"] = SESSION_ID;
  }
  if (AUTH_TOKEN) {
    proxyHeaders["authorization"] =
      AUTH_TOKEN.startsWith("Bearer ") || AUTH_TOKEN.startsWith("bearer ")
        ? AUTH_TOKEN
        : `Bearer ${AUTH_TOKEN}`;
  }

  console.log(`[Proxy] [#${reqId}] ${clientIp} --> ${req.method} ${reqUrl} -> ${targetBase.origin}${proxyPath}`);

  const options = {
    protocol: targetBase.protocol,
    hostname: targetBase.hostname,
    port: targetBase.port || (isHttps ? 443 : 80),
    path: proxyPath,
    method: req.method,
    headers: proxyHeaders,
    servername: targetBase.hostname, // HTTPS SNI
  };

  const proxyReq = client.request(options, (proxyRes) => {
    const elapsed = Date.now() - startTime;
    const statusCode = proxyRes.statusCode || 200;
    const isSse = proxyRes.headers["content-type"]?.includes("text/event-stream");

    console.log(`[Proxy] [#${reqId}] <-- ${req.method} ${reqUrl} -> ${statusCode} ${proxyRes.statusMessage || ""} (${elapsed}ms)${isSse ? " [SSE Stream]" : ""}`);

    // 4. 追加宽松 CORS 响应头，确保前端浏览器正常接收
    const responseHeaders = { ...proxyRes.headers };
    responseHeaders["access-control-allow-origin"] = origin || "*";
    responseHeaders["access-control-allow-credentials"] = "true";

    res.writeHead(statusCode, responseHeaders);

    // 5. 流式透传响应数据（支持 SSE 交互流与文件下载）
    proxyRes.pipe(res);

    if (isSse) {
      res.on("close", () => {
        console.log(`[Proxy] [#${reqId}] SSE stream closed (total ${Date.now() - startTime}ms)`);
      });
    }
  });

  proxyReq.on("error", (err) => {
    const elapsed = Date.now() - startTime;
    console.error(`[Proxy Error] [#${reqId}] 转发失败 (${req.method} ${proxyPath}): ${err.message} (${elapsed}ms)`);
    if (!res.headersSent) {
      setCorsHeaders(res, origin);
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          error: "AgentArts 代理转发失败",
          target: TARGET_URL,
          path: proxyPath,
          detail: err.message,
        })
      );
    }
  });

  req.on("error", (err) => {
    console.error(`[Proxy Error] [#${reqId}] 客户端连接异常: ${err.message}`);
    proxyReq.destroy(err);
  });

  // 6. 流式透传请求体（文件上传、POST payload 等）
  req.pipe(proxyReq);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 本地请求转发代理已在 http://0.0.0.0:${PORT} 启动，转发至: ${TARGET_URL}`);
});
