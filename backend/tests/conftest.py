"""Pytest fixtures — isolated SQLite database, no external services required."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["JWT_SECRET"] = "test-secret-key-not-for-production-use-32"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
if not os.environ.get("RUN_MYSQL_TESTS"):
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id.apps.googleusercontent.com"
os.environ["STRIPE_API_KEY"] = ""
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
os.environ["DB_PASSWORD"] = ""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.utils import new_id, utcnow
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.property import Property
from app.models.user import User

get_settings.cache_clear()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _create_user(
    session: AsyncSession,
    *,
    role: str = "buyer",
    email: str | None = None,
    name: str = "Test User",
) -> User:
    user = User(
        id=new_id("user"),
        email=email or f"{new_id('mail')}@example.com",
        name=name,
        role=role,
        created_at=utcnow(),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def auth_header(user: User) -> dict:
    token, _ = create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def buyer(db_session) -> User:
    return await _create_user(db_session, role="buyer", name="Buyer", email="buyer@example.com")


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    return await _create_user(db_session, role="owner", name="Owner", email="owner@example.com")


@pytest_asyncio.fixture
async def other_buyer(db_session) -> User:
    return await _create_user(db_session, role="buyer", name="Other", email="other@example.com")


@pytest_asyncio.fixture
async def published_property(db_session, owner) -> Property:
    prop = Property(
        id=new_id("prop"),
        owner_id=owner.id,
        title="Sunny Apartment",
        description="A lovely place with lots of light and space for a family.",
        address="123 Main St, Springfield",
        latitude=40.7,
        longitude=-74.0,
        price=500000,
        property_type="apartment",
        area_sqft=1200,
        bedrooms=2,
        bathrooms=2,
        amenities=["parking", "gym"],
        images=[],
        status="published",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


@pytest.fixture
def tomorrow_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat() + "T10:00:00+00:00"
