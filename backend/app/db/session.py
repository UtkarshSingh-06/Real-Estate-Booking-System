"""Async database engine and session management."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

connect_args = {}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.sqlalchemy_database_url,
    echo=settings.debug,
    pool_pre_ping=not settings.is_sqlite,
    pool_recycle=3600 if not settings.is_sqlite else None,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables in local/test only. Production must use Alembic migrations."""
    import logging

    from app.core.config import get_settings

    settings = get_settings()
    if settings.environment.lower() in ("production", "staging"):
        logging.getLogger(__name__).info(
            "Skipping create_all in %s — run `alembic upgrade head` before serving traffic",
            settings.environment,
        )
        return

    from app.db import models  # noqa: F401
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
