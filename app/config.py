import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = "DeepAgent API"
    VERSION: str = "0.1.0"
    HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8123"))
    PORT: int = FASTAPI_PORT

    # 规范统一的 RESTful API 路由前缀
    API_PREFIX: str = os.getenv("API_PREFIX", "/api").rstrip("/")

    # CopilotKit UI 交互协议专属端点路径 (统一由 API_PREFIX 拼接)
    COPILOTKIT_BASE_PATH: str = f"{API_PREFIX}/copilotkit"

    # Database & Persistence (PostgreSQL)
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "deepagent")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "deepagent")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "deepagent_secret")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgres://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
    )

    # LLM Settings
    MODEL_NAME: str = os.getenv("MODEL_NAME", "deepseek-v4.1-flash-1017")
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "deepseek")
    MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "https://api.modelarts-maas.com/plan/v2")
    MODEL_API_KEY: str = os.getenv("MODEL_API_KEY", os.getenv("OPENAI_API_KEY", ""))

    # Upload Directory
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")

    # AgentArts Sandbox Settings
    AGENTARTS_CODE_INTERPRETER_NAME: str = os.getenv(
        "AGENTARTS_CODE_INTERPRETER_NAME", "deepagent-sandbox"
    )
    AGENTARTS_CODEINTERPRETER_DATA_ENDPOINT: str = os.getenv(
        "AGENTARTS_CODEINTERPRETER_DATA_ENDPOINT", ""
    )
    AGENTARTS_REGION: str = os.getenv("AGENTARTS_REGION", "cn-southwest-2")
    AGENTARTS_WORKSPACE: str = os.getenv("AGENTARTS_WORKSPACE", "/home/user")
    AGENTARTS_SESSION_TIMEOUT: int = int(os.getenv("AGENTARTS_SESSION_TIMEOUT", "3600"))

    # AgentArts Browser Settings
    AGENTARTS_BROWSER_NAME: str = os.getenv("AGENTARTS_BROWSER_NAME", "deepagent-browser")
    AGENTARTS_BROWSER_DATA_ENDPOINT: str = os.getenv(
        "AGENTARTS_BROWSER_DATA_ENDPOINT",
        "",
    )
    AGENTARTS_BROWSER_AUTH_TYPE: str = os.getenv("AGENTARTS_BROWSER_AUTH_TYPE", "IAM")
    AGENTARTS_BROWSER_SESSION_TIMEOUT: int = int(
        os.getenv("AGENTARTS_BROWSER_SESSION_TIMEOUT", "900")
    )
    AGENTARTS_BROWSER_BRIDGE_PORT: int = int(os.getenv("AGENTARTS_BROWSER_BRIDGE_PORT", "9223"))
    AGENTARTS_BROWSER_BRIDGE_HOST: str = os.getenv("AGENTARTS_BROWSER_BRIDGE_HOST", "127.0.0.1")

    # AgentArts Long-term Memory Settings
    AGENTARTS_MEMORY_SPACE_ID: str = os.getenv("AGENTARTS_MEMORY_SPACE_ID", "")
    AGENTARTS_MEMORY_API_KEY: str = os.getenv(
        "AGENTARTS_MEMORY_API_KEY", os.getenv("HUAWEICLOUD_SDK_MEMORY_API_KEY", "")
    )
    AGENTARTS_MEMORY_TOP_K: int = int(os.getenv("AGENTARTS_MEMORY_TOP_K", "5"))

    # Agent Settings
    DEFAULT_AGENT_ID: str = "sample_agent"
    AGENT_RECURSION_LIMIT: int = int(os.getenv("AGENT_RECURSION_LIMIT", "100"))
    SYSTEM_PROMPT: str = (
        "You are DeepAgent, an advanced AI research assistant with multimodal, filesystem, and browser capabilities. "
        "You operate in a Linux sandbox environment where the default workspace directory is `/home/user`. "
        "All created files and project work should be located under `/home/user`. "
        "You have access to filesystem tools including `read_file`, `write_file`, `edit_file`, `ls`, `glob`, and `grep`. "
        "When the user uploads directly readable files (such as TXT, Markdown, CSV, JSON, and source code files), "
        "their storage paths are provided in the message. You should proactively use the built-in `read_file` tool "
        "to inspect their contents on demand. "
        "You also have access to `browser_use` for web browsing and web automation via agent-browser CLI connected to a remote cloud browser. "
        "You can open URLs, take snapshots to inspect pages and find element references (@e1, @e2, etc.), click elements, fill forms, extract text, and take screenshots. "
        "You can plan complex steps, call available tools, and provide clear, detailed, and accurate insights."
    )


settings = Settings()
