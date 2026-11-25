#!/bin/bash
set -e

# Trap signals for graceful shutdown
cleanup() {
    echo "[Entrypoint] Stopping all background services..."
    kill -TERM "$AGENT_PID" "$RUNTIME_PID" "$CADDY_PID" 2>/dev/null || true
    wait "$AGENT_PID" "$RUNTIME_PID" "$CADDY_PID" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

FASTAPI_P="${FASTAPI_PORT:-8123}"
GATEWAY_P="${GATEWAY_PORT:-4000}"
CADDY_P="${PORT:-8000}"

mkdir -p /app/logs

echo "[Entrypoint] Starting FastAPI Agent on 127.0.0.1:${FASTAPI_P}..."
PYTHONUNBUFFERED=1 uv run --no-sync main.py 2>&1 | tee -a /app/logs/agent.log &
AGENT_PID=$!

echo "[Entrypoint] Starting Node.js CopilotKit Runtime on 127.0.0.1:${GATEWAY_P}..."
node src/server.mjs 2>&1 | tee -a /app/logs/runtime.log &
RUNTIME_PID=$!

# 等待真实后端 FastAPI 就绪，实时监控进程状态
echo "[Entrypoint] Waiting for FastAPI backend to be ready on 127.0.0.1:${FASTAPI_P}..."
MAX_RETRIES=60
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    # 1. 检查 FastAPI 进程是否异常崩溃退出
    if ! kill -0 "$AGENT_PID" 2>/dev/null; then
        echo "[Entrypoint] ❌ ERROR: FastAPI backend process (PID: $AGENT_PID) exited unexpectedly!"
        echo "==================== [FastAPI Crash Logs] ===================="
        tail -n 50 /app/logs/agent.log 2>/dev/null || true
        echo "=============================================================="
        cleanup
        exit 1
    fi

    # 2. 探活检查
    if curl -s -f "http://127.0.0.1:${FASTAPI_P}/ping" >/dev/null 2>&1; then
        echo "[Entrypoint] ✅ FastAPI backend is healthy and verified on port ${FASTAPI_P}."
        break
    fi

    sleep 0.5
    COUNT=$((COUNT + 1))
done

if [ $COUNT -ge $MAX_RETRIES ]; then
    echo "[Entrypoint] ❌ ERROR: FastAPI backend failed to respond on port ${FASTAPI_P} within 30s."
    echo "==================== [FastAPI Last Logs] ===================="
    tail -n 50 /app/logs/agent.log 2>/dev/null || true
    echo "============================================================="
    cleanup
    exit 1
fi

echo "[Entrypoint] Starting Caddy unified gateway on port ${CADDY_P}..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

wait -n "$AGENT_PID" "$RUNTIME_PID" "$CADDY_PID"
EXIT_CODE=$?

echo "[Entrypoint] A service exited with code ${EXIT_CODE}."
cleanup
