"""FastAPI application factory and ASGI entrypoints."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import init_db
from app.routers import ai_analytics, auth, bookings, messages, payments, properties
from app.websocket.server import create_sio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    try:
        await init_db()
        logger.info("Database ready (%s)", settings.environment)
    except Exception:
        logger.exception("Database initialization failed")
        raise
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url="/api/redoc" if settings.environment != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Stripe-Signature"],
    )

    register_exception_handlers(app)

    api = settings.api_prefix.rstrip("/") or "/api"
    app.include_router(auth.router, prefix=api)
    app.include_router(properties.router, prefix=api)
    app.include_router(bookings.router, prefix=api)
    app.include_router(payments.router, prefix=api)
    app.include_router(messages.router, prefix=api)
    app.include_router(ai_analytics.router, prefix=api)

    @app.get(f"{api}/")
    async def root():
        return {"message": f"{settings.app_name} API"}

    @app.get(f"{api}/health")
    async def health():
        return {"status": "healthy", "environment": settings.environment}

    return app


app = create_app()
sio = create_sio()
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
