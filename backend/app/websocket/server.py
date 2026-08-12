"""Authenticated Socket.IO server — identity is derived server-side from JWT."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

import socketio
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.messaging import Conversation
from app.models.user import User, UserSession
from app.services.messaging import user_in_conversation

logger = logging.getLogger(__name__)

_sio: Optional[socketio.AsyncServer] = None
# sid -> authenticated user_id
_sid_users: Dict[str, str] = {}


def create_sio() -> socketio.AsyncServer:
    global _sio
    settings = get_settings()
    _sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=settings.cors_origins_list,
        logger=settings.debug,
        engineio_logger=settings.debug,
    )
    register_handlers(_sio)
    return _sio


def get_sio() -> socketio.AsyncServer:
    global _sio
    if _sio is None:
        return create_sio()
    return _sio


def _extract_token(auth: Any, environ: dict) -> Optional[str]:
    if isinstance(auth, dict):
        token = auth.get("token") or auth.get("session_token")
        if token:
            return str(token)
    query = environ.get("QUERY_STRING") or ""
    params = parse_qs(query)
    for key in ("token", "session_token", "auth"):
        if key in params and params[key]:
            return params[key][0]
    # Authorization header from Engine.IO polling upgrade
    headers = environ.get("HTTP_AUTHORIZATION") or environ.get("headers")
    if isinstance(headers, str) and headers.startswith("Bearer "):
        return headers[7:].strip()
    return None


async def _resolve_user_id(token: str) -> Optional[str]:
    settings = get_settings()
    try:
        payload = decode_access_token(token, settings)
        user_id = payload.get("user_id")
        if user_id:
            return str(user_id)
    except Exception:
        pass

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserSession).where(UserSession.session_token == token)
            )
            session = result.scalar_one_or_none()
            if session:
                return session.user_id
    except Exception:
        logger.debug("Socket session lookup failed", exc_info=True)
    return None


def register_handlers(sio: socketio.AsyncServer) -> None:
    @sio.event
    async def connect(sid, environ, auth=None):
        token = _extract_token(auth, environ)
        if not token:
            logger.warning("Socket connect rejected: missing token (%s)", sid)
            return False
        user_id = await _resolve_user_id(token)
        if not user_id:
            logger.warning("Socket connect rejected: invalid token (%s)", sid)
            return False

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            if not result.scalar_one_or_none():
                return False

        _sid_users[sid] = user_id
        await sio.save_session(sid, {"user_id": user_id})
        await sio.enter_room(sid, f"user:{user_id}")
        logger.info("Socket connected user=%s sid=%s", user_id, sid)
        return True

    @sio.event
    async def disconnect(sid):
        user_id = _sid_users.pop(sid, None)
        logger.info("Socket disconnected user=%s sid=%s", user_id, sid)

    @sio.event
    async def join_room(sid, data):
        """Join own user room only. Client-provided user_id is ignored."""
        session = await sio.get_session(sid)
        user_id = session.get("user_id") or _sid_users.get(sid)
        if not user_id:
            return {"ok": False, "error": "unauthenticated"}
        await sio.enter_room(sid, f"user:{user_id}")
        return {"ok": True, "room": f"user:{user_id}"}

    @sio.event
    async def join_conversation(sid, data):
        session = await sio.get_session(sid)
        user_id = session.get("user_id") or _sid_users.get(sid)
        if not user_id:
            return {"ok": False, "error": "unauthenticated"}
        conversation_id = (data or {}).get("conversation_id")
        if not conversation_id:
            return {"ok": False, "error": "conversation_id required"}

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if not conv or not user_in_conversation(conv, user_id):
                return {"ok": False, "error": "forbidden"}

        await sio.enter_room(sid, f"conversation:{conversation_id}")
        return {"ok": True}

    @sio.event
    async def send_message(sid, data):
        """Realtime fan-out is server-authoritative via REST; this rejects spoofed sends."""
        session = await sio.get_session(sid)
        user_id = session.get("user_id") or _sid_users.get(sid)
        if not user_id:
            return {"ok": False, "error": "unauthenticated"}
        # Do not trust client payload as a persisted message. Clients should use REST.
        # Optionally echo typing-style ephemeral events only when sender matches.
        payload = data or {}
        if payload.get("sender_id") and payload.get("sender_id") != user_id:
            return {"ok": False, "error": "forbidden"}
        receiver_id = payload.get("receiver_id")
        if not receiver_id:
            return {"ok": False, "error": "receiver_id required"}
        # Ephemeral notify only — persistence is via HTTP API
        await sio.emit(
            "new_message",
            {**payload, "sender_id": user_id},
            room=f"user:{receiver_id}",
        )
        return {"ok": True}

    @sio.event
    async def typing(sid, data):
        session = await sio.get_session(sid)
        user_id = session.get("user_id") or _sid_users.get(sid)
        if not user_id:
            return {"ok": False, "error": "unauthenticated"}
        payload = data or {}
        receiver_id = payload.get("receiver_id")
        if not receiver_id:
            return {"ok": False, "error": "receiver_id required"}
        await sio.emit(
            "user_typing",
            {
                "user_id": user_id,
                "receiver_id": receiver_id,
                "conversation_id": payload.get("conversation_id"),
            },
            room=f"user:{receiver_id}",
        )
        return {"ok": True}


async def emit_new_message(message: dict, receiver_id: str) -> None:
    sio = get_sio()
    await sio.emit("new_message", message, room=f"user:{receiver_id}")
    conversation_id = message.get("conversation_id")
    if conversation_id:
        await sio.emit("new_message", message, room=f"conversation:{conversation_id}")
