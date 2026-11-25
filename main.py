"""
Main entrypoint for DeepAgent application.
Re-exports `app` and `agent` for LangGraph CLI and uvicorn runners.
"""

import logging

logging.basicConfig(level=logging.INFO)

from app.main import app
from app.agent.agent import agent
from app.config import settings

if __name__ == "__main__":
    import os
    import uvicorn

    is_production = os.getenv("NODE_ENV") == "production"

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.FASTAPI_PORT,
        reload=not is_production,
        reload_dirs=["app"] if not is_production else None,
        reload_excludes=["logs/*", "*.log", "*.db*"] if not is_production else None,
        loop="uvloop",
    )
