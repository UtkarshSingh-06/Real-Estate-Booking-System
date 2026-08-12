"""Messaging routes with conversation authorization."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.messaging import MessageCreate
from app.schemas.user import UserOut
from app.services import messaging as messaging_service
from app.websocket.server import emit_new_message

router = APIRouter(tags=["messages"])


@router.get("/conversations")
async def list_conversations(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await messaging_service.list_conversations(db, user, page, page_size)
    return {
        "conversations": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    items, total = await messaging_service.list_messages(
        db, user, conversation_id, page, page_size
    )
    return {
        "messages": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.post("/messages")
async def send_message(
    body: MessageCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    message, meta = await messaging_service.send_message(db, user, body)
    await emit_new_message(message, body.receiver_id)
    return meta


@router.put("/messages/{message_id}/read")
async def mark_read(
    message_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await messaging_service.mark_read(db, user, message_id)
