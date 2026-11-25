from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from app.agent.agent import agent
from app.config import settings
from app.database import TORTOISE_ORM
from app.dependencies import get_current_user_id
from app.routers.threads import router as threads_router
from app.routers.upload import router as upload_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="FastAPI Deep Agent with Tortoise ORM & CopilotKit AG-UI support.",
    )

    # CORS 配置
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Tortoise ORM 注册与生命周期管理
    register_tortoise(
        application,
        config=TORTOISE_ORM,
        generate_schemas=True,
        add_exception_handlers=True,
    )

    @application.on_event("startup")
    async def on_startup():
        from app.database import get_checkpointer

        await get_checkpointer().ensure_setup()

    # 0. 基础探活接口 (无需前缀，直接响应 /ping)
    @application.get("/ping", tags=["Health"])
    def ping():
        return {"status": "Healthy"}

    # 1. 公开的健康探活接口 (无需 Header 鉴权)
    @application.get(f"{settings.API_PREFIX}/health", tags=["Health"])
    def health():
        return {
            "status": "ok",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "api_prefix": settings.API_PREFIX,
        }

    # 2. 规范统一的 RESTful 业务数据路由组 (全部统一在 /api 前缀下，在顶层依赖中统一强制校验 X-User-Id)
    api_router = APIRouter(
        prefix=settings.API_PREFIX,
        dependencies=[Depends(get_current_user_id)],
    )
    api_router.include_router(threads_router, prefix="/threads")
    api_router.include_router(upload_router, prefix="/upload")

    application.include_router(api_router)

    # 3. 挂载 LangGraph AG-UI 智能体（用于 4000 端口 Node.js UI 运行时桥接）
    add_langgraph_fastapi_endpoint(
        app=application,
        agent=LangGraphAGUIAgent(
            name=settings.DEFAULT_AGENT_ID,
            description="Deep Agent with PostgreSQL checkpointer.",
            graph=agent,
            config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
        ),
        path="/",
    )

    return application


app = create_app()
