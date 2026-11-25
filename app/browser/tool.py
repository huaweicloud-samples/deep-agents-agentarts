"""Agent tool for browser automation using agent-browser CLI connected to AgentArts cloud browser."""

from __future__ import annotations

import logging
from app.browser.manager import browser_manager

logger = logging.getLogger(__name__)


def browser_use(command: str) -> str:
    """Execute browser automation commands via agent-browser CLI connected to remote cloud browser.

    Supported commands include:
    - open <url>: Navigate to a web page (e.g. 'open https://example.com')
    - snapshot [-i]: Inspect the accessibility tree and get interactive element references (@e1, @e2, ...)
    - click <ref|selector>: Click an element (e.g. 'click @e1')
    - fill <ref|selector> <text>: Clear and fill text into an input field (e.g. 'fill @e2 "search query"')
    - type <ref|selector> <text>: Type text into an element without clearing
    - press <key>: Press keyboard key (e.g. 'press Enter', 'press Tab')
    - scroll <up|down> [pixels]: Scroll page (e.g. 'scroll down 500')
    - wait <selector|ms>: Wait for element or duration (e.g. 'wait 2000', 'wait networkidle')
    - get <text|title|url|html|value> [selector]: Extract text or attributes (e.g. 'get title', 'get text @e1')
    - screenshot [path]: Capture a screenshot of the current page
    - eval <javascript>: Run JavaScript in the page
    - close: Close the browser session

    Args:
        command: The browser command to execute (e.g. 'open https://example.com', 'snapshot -i', 'click @e1').

    Returns:
        The execution output from the browser command.
    """
    return browser_manager.execute(command)
