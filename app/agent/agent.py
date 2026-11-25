from typing import Any, TypedDict

from copilotkit import CopilotKitMiddleware, CopilotKitState
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from app.agent.multimodal import MultimodalProcessorMiddleware
from app.agent.tools import AVAILABLE_TOOLS
from app.config import settings
from app.database import get_checkpointer
from app.memory.middleware import LongTermMemoryMiddleware
from app.sandbox.backend import AgentArtsBackend
from app.sandbox.manager import sandbox_manager
from app.sandbox.middleware import SandboxLifecycleMiddleware


class AgentState(CopilotKitState):
    sandbox_session_id: str | None
    long_term_memory: str | None


class AgentContext(TypedDict, total=False):
    output_schema: dict[str, Any]


def create_agent():
    chat_model = init_chat_model(
        model=settings.MODEL_NAME,
        model_provider=settings.MODEL_PROVIDER,
        base_url=settings.MODEL_BASE_URL if settings.MODEL_BASE_URL else None,
        api_key=settings.MODEL_API_KEY,
    )

    checkpointer = get_checkpointer()
    sandbox_backend = AgentArtsBackend(manager=sandbox_manager)

    return create_deep_agent(
        model=chat_model,
        tools=AVAILABLE_TOOLS,
        backend=sandbox_backend,
        middleware=[
            SandboxLifecycleMiddleware(manager=sandbox_manager),
            LongTermMemoryMiddleware(),
            MultimodalProcessorMiddleware(),
            CopilotKitMiddleware(),
        ],
        context_schema=AgentContext,
        state_schema=AgentState,
        system_prompt=settings.SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


agent = create_agent()
