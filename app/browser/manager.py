"""Browser session manager for AgentArts Browser and agent-browser CLI.

Manages 1-to-1 binding between LangGraph thread_id and agent-browser CLI sessions,
using the native agentarts provider plugin on a static port bridge.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess

from langgraph.config import get_config

from app.config import settings

logger = logging.getLogger(__name__)


def _sanitize_session_id(thread_id: str) -> str:
    """Sanitize thread_id to be safe for AgentArts session_name and agent-browser --session.

    Pattern: only [a-zA-Z0-9_-], max length 128 chars.
    """
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", thread_id.strip())
    if not clean:
        return "default"
    return clean[:128]


class BrowserManager:
    """Manages thread-scoped browser instances using agent-browser provider plugin."""

    def __init__(self) -> None:
        pass

    def _get_current_thread_id(self) -> str:
        """Retrieve thread_id from LangGraph execution context or fallback to 'default'."""
        try:
            config = get_config()
            tid = config.get("configurable", {}).get("thread_id")
            if tid:
                return str(tid)
        except Exception:
            pass
        return "default"

    def _get_env(self) -> dict[str, str]:
        """Construct environment variables for agent-browser execution."""
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        env = os.environ.copy()
        env["AGENT_BROWSER_PROVIDER"] = "agentarts"
        # Point to project agent-browser.json plugin definition
        cfg_path = os.path.abspath("agent-browser.json")
        if os.path.exists(cfg_path):
            env["AGENT_BROWSER_CONFIG"] = cfg_path
        env["AGENT_BROWSER_SCREENSHOT_DIR"] = settings.UPLOAD_DIR
        return env

    def execute(
        self, command: str, thread_id: str | None = None, timeout: int = 60
    ) -> str:
        """Execute a browser automation command via agent-browser CLI using agentarts provider plugin.

        Args:
            command: The command string (e.g. 'open https://example.com', 'snapshot -i', 'click @e1').
            thread_id: Optional thread ID (auto-resolved from LangGraph context if None).
            timeout: Command timeout in seconds.

        Returns:
            Command execution output string.
        """
        tid = thread_id or self._get_current_thread_id()
        session_name = _sanitize_session_id(tid)

        clean_cmd = command.strip()
        if clean_cmd.startswith("agent-browser "):
            clean_cmd = clean_cmd[len("agent-browser ") :].strip()

        if clean_cmd == "close":
            logger.info("Closing browser session for thread '%s'", tid)
            self.release(tid)
            return "Browser session closed successfully."

        env = self._get_env()
        args = shlex.split(clean_cmd)
        argv = ["agent-browser", "--session", session_name] + args

        res = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env
        )

        stdout = res.stdout.strip()
        stderr = res.stderr.strip()

        if res.returncode == 0:
            return stdout or stderr or f"Command '{clean_cmd}' completed successfully."

        error_details = stderr if stderr else stdout
        return f"Error (exit code {res.returncode}): {error_details}"

    def release(self, thread_id: str) -> None:
        """Close agent-browser CLI daemon and terminate the cloud browser session via provider plugin."""
        session_name = _sanitize_session_id(thread_id)
        env = self._get_env()

        try:
            subprocess.run(
                ["agent-browser", "--session", session_name, "close"],
                capture_output=True,
                text=True,
                timeout=15,
                env=env,
            )
        except Exception as exc:
            logger.debug(
                "Error closing agent-browser session '%s': %s", session_name, exc
            )


browser_manager = BrowserManager()
