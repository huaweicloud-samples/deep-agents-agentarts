"""Static port WebSocket bridge for AgentArts Cloud Browser CDP sessions.

Listens on a fixed port (default 127.0.0.1:9223) and proxies incoming
CDP WebSocket connections from agent-browser to the upstream Huawei Cloud
AgentArts automation stream, automatically injecting required authentication headers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
import time
from typing import Any, Dict

import websockets

from app.config import settings

logger = logging.getLogger("app.browser.bridge")

SESSIONS_FILE = "/tmp/agentarts_bridge_sessions.json"
BRIDGE_HOST = settings.AGENTARTS_BROWSER_BRIDGE_HOST
BRIDGE_PORT = settings.AGENTARTS_BROWSER_BRIDGE_PORT


def _load_sessions() -> Dict[str, Any]:
    if not os.path.exists(SESSIONS_FILE):
        return {}
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_sessions(sessions: Dict[str, Any]) -> None:
    tmp_path = f"{SESSIONS_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(sessions, f)
    os.replace(tmp_path, SESSIONS_FILE)


def register_session(session_name: str, ws_url: str, ws_headers: dict) -> None:
    """Register or update an AgentArts session endpoint and its headers."""
    sessions = _load_sessions()
    # Filter out hop-by-hop headers managed by the client websocket library
    hop_by_hop = {
        "upgrade",
        "connection",
        "sec-websocket-version",
        "sec-websocket-key",
        "host",
    }
    filtered_headers = {
        k: v for k, v in ws_headers.items() if k.lower() not in hop_by_hop
    }

    sessions[session_name] = {
        "ws_url": ws_url,
        "ws_headers": filtered_headers,
        "updated_at": time.time(),
    }
    _save_sessions(sessions)


def unregister_session(session_name: str) -> None:
    """Remove a session from registry."""
    sessions = _load_sessions()
    if session_name in sessions:
        sessions.pop(session_name, None)
        _save_sessions(sessions)


def is_bridge_running(host: str = BRIDGE_HOST, port: int = BRIDGE_PORT) -> bool:
    """Check if static bridge port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def ensure_bridge_running(host: str = BRIDGE_HOST, port: int = BRIDGE_PORT) -> None:
    """Ensure the static bridge server process is running in the background."""
    if is_bridge_running(host, port):
        return

    # Launch bridge server as detached background process
    log_file = "/tmp/agentarts_bridge.log"
    out = open(log_file, "a", encoding="utf-8")
    subprocess_env = os.environ.copy()
    subprocess_env["PYTHONUNBUFFERED"] = "1"

    import subprocess

    subprocess.Popen(
        [sys.executable, "-m", "app.browser.bridge"],
        stdout=out,
        stderr=out,
        start_new_session=True,
        env=subprocess_env,
    )

    # Wait up to 3 seconds for port to open
    start = time.time()
    while time.time() - start < 3.0:
        if is_bridge_running(host, port):
            return
        time.sleep(0.05)

    if not is_bridge_running(host, port):
        raise RuntimeError(f"Failed to start AgentArts static bridge on {host}:{port}")


async def bridge_handler(client_ws: Any) -> None:
    """Handle incoming agent-browser CDP connection and proxy to cloud browser."""
    path = getattr(client_ws.request, "path", "/").strip("/")

    sessions = _load_sessions()
    session_info = None

    if path and path in sessions:
        session_info = sessions[path]
    elif len(sessions) == 1:
        # Fallback to single active session if path omitted
        session_info = next(iter(sessions.values()))

    if not session_info:
        logger.error("No registered AgentArts session found for path '%s'", path)
        await client_ws.close(1008, f"Session '{path}' not found")
        return

    upstream_url = session_info["ws_url"]
    upstream_headers = session_info["ws_headers"]

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers=upstream_headers,
            max_size=None,
            ping_interval=None,
            open_timeout=15,
        ) as upstream_ws:

            async def forward(src: Any, dst: Any) -> None:
                try:
                    async for msg in src:
                        await dst.send(msg)
                except Exception:
                    pass

            await asyncio.gather(
                forward(client_ws, upstream_ws),
                forward(upstream_ws, client_ws),
            )
    except Exception as exc:
        logger.error(
            "Bridge proxy error connecting to upstream %s: %s", upstream_url, exc
        )
        await client_ws.close(1011, f"Upstream connect error: {exc}")


async def run_server() -> None:
    """Run bridge WebSocket server forever."""
    server = await websockets.serve(
        bridge_handler,
        BRIDGE_HOST,
        BRIDGE_PORT,
        max_size=None,
        ping_interval=None,
    )
    logger.info(
        "AgentArts static CDP bridge listening on %s:%d", BRIDGE_HOST, BRIDGE_PORT
    )
    await server.wait_closed()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_server())
