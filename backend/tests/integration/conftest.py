"""MySQL integration test fixtures."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

RUN_MYSQL = os.environ.get("RUN_MYSQL_TESTS", "").lower() in ("1", "true", "yes")

MYSQL_URL = os.environ.get(
    "MYSQL_TEST_URL",
    "mysql+aiomysql://root:testpassword@127.0.0.1:3307/realestate_test",
)

if RUN_MYSQL:
    os.environ["DATABASE_URL"] = MYSQL_URL

from app.db import models  # noqa: F401 — register tables on Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def mysql_engine():
    if not RUN_MYSQL:
        pytest.skip("MySQL integration tests disabled")
    get_settings.cache_clear()
    engine = create_async_engine(MYSQL_URL, echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def mysql_client(mysql_engine):
    Session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    get_settings.cache_clear()
    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    get_settings.cache_clear()
