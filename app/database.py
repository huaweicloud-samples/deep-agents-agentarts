"""Database and checkpointer configuration for PostgreSQL."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres import BasePostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

TORTOISE_ORM = {
    "connections": {
        "default": settings.DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": ["app.models.thread"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "UTC",
}


class LocalAsyncPostgresSaver(AsyncPostgresSaver):
    """An AsyncPostgresSaver with lazy initialization for event loop and connection pool,
    allowing instantiation at module-level import before the event loop starts."""

    def __init__(self, conn_string: str) -> None:
        BasePostgresSaver.__init__(self, serde=JsonPlusSerializer())
        self.conn_string = conn_string
        self._pool: AsyncConnectionPool | None = None
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_setup = False
        self.pipe = None
        self.supports_pipeline = False

    @property
    def conn(self) -> AsyncConnectionPool:
        if self._pool is None:
            self._pool = AsyncConnectionPool(
                self.conn_string,
                open=False,
                kwargs={
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
            )
        return self._pool

    @conn.setter
    def conn(self, val: AsyncConnectionPool) -> None:
        self._pool = val

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @lock.setter
    def lock(self, val: asyncio.Lock) -> None:
        self._lock = val

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        return self._loop

    @loop.setter
    def loop(self, val: asyncio.AbstractEventLoop | None) -> None:
        self._loop = val

    async def ensure_setup(self) -> None:
        """Ensure connection pool is opened and LangGraph tables are migrated."""
        if self._is_setup:
            return
        async with self.lock:
            if not self._is_setup:
                if self.conn.closed:
                    await self.conn.open()
                self._is_setup = True
                await self.setup()

    @asynccontextmanager
    async def _cursor(self, *, pipeline: bool = False):
        await self.ensure_setup()
        async with super()._cursor(pipeline=pipeline) as cur:
            yield cur


_checkpointer: LocalAsyncPostgresSaver | None = None


def get_checkpointer() -> LocalAsyncPostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = LocalAsyncPostgresSaver(settings.DATABASE_URL)
    return _checkpointer
