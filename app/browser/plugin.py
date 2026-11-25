"""AgentArts Browser Provider Plugin for agent-browser CLI.

Implements agent-browser.plugin.v1 stdio JSON protocol with browser.provider capability.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback

from agentarts.sdk.tools.browser import Browser

from app.browser.bridge import (
    BRIDGE_HOST,
    BRIDGE_PORT,
    ensure_bridge_running,
    register_session,
    unregister_session,
)
from app.config import settings

logger = logging.getLogger("app.browser.plugin")


def handle_manifest() -> dict:
    return {
        "protocol": "agent-browser.plugin.v1",
        "success": True,
        "data": {
            "name": "agentarts",
            "capabilities": ["browser.provider"],
        },
    }


def handle_launch(request: dict) -> dict:
    session_name = request.get("session") or "default"

    # Start or attach to AgentArts Cloud Browser session
    client = Browser(
        region=settings.AGENTARTS_REGION,
        data_endpoint=settings.AGENTARTS_BROWSER_DATA_ENDPOINT,
        auth_type=settings.AGENTARTS_BROWSER_AUTH_TYPE,
    )

    client.start_session(
        browser_name=settings.AGENTARTS_BROWSER_NAME,
        session_name=session_name,
        session_timeout=settings.AGENTARTS_BROWSER_SESSION_TIMEOUT,
    )

    ws_url, ws_headers = client.generate_automation_url()

    # Register session with static bridge
    register_session(session_name, ws_url, ws_headers)

    # Ensure static bridge server is listening
    ensure_bridge_running(BRIDGE_HOST, BRIDGE_PORT)

    cdp_url = f"ws://{BRIDGE_HOST}:{BRIDGE_PORT}/{session_name}"

    return {
        "protocol": "agent-browser.plugin.v1",
        "success": True,
        "data": {
            "cdpUrl": cdp_url,
        },
    }


def handle_close(request: dict) -> dict:
    session_name = request.get("session") or "default"
    unregister_session(session_name)

    try:
        client = Browser(
            region=settings.AGENTARTS_REGION,
            data_endpoint=settings.AGENTARTS_BROWSER_DATA_ENDPOINT,
            auth_type=settings.AGENTARTS_BROWSER_AUTH_TYPE,
        )
        # Attempt to stop session on AgentArts cloud
        client.stop_session()
    except Exception:
        pass

    return {
        "protocol": "agent-browser.plugin.v1",
        "success": True,
        "data": {},
    }


def main() -> None:
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        resp = handle_manifest()
        sys.stdout.write(json.dumps(resp))
        sys.stdout.flush()
        return

    try:
        payload = json.loads(raw_input)
        req_type = payload.get("type")
        request = payload.get("request") or {}

        if req_type == "plugin.manifest":
            resp = handle_manifest()
        elif req_type == "browser.launch":
            resp = handle_launch(request)
        elif req_type == "browser.close":
            resp = handle_close(request)
        else:
            resp = {
                "protocol": "agent-browser.plugin.v1",
                "success": True,
                "data": {},
            }

    except Exception as exc:
        resp = {
            "protocol": "agent-browser.plugin.v1",
            "success": False,
            "error": f"{exc}\n{traceback.format_exc()}",
        }

    sys.stdout.write(json.dumps(resp))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
