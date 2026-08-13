"""MySQL integration test fixtures."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

RUN_MYSQL = os.environ.get("RUN_MYSQL_TESTS", "").lower() in ("1", "true", "yes")

MYSQL_URL = os.environ.get(
    "MYSQL_TEST_URL",
    "mysql+aiomysql://root:testpassword@127.0.0.1:3307/realestate_test",
)

if RUN_MYSQL:
    os.environ["DATABASE_URL"] = MYSQL_URL

# Import models only — avoid importing app.main (binds a global engine to this loop)
from app.db import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base


@pytest_asyncio.fixture
async def mysql_engine():
    if not RUN_MYSQL:
        pytest.skip("MySQL integration tests disabled")
    get_settings.cache_clear()
    engine = create_async_engine(
        MYSQL_URL,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield engine
    await engine.dispose()
