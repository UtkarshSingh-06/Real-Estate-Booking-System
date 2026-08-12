"""Messaging service with participant authorization."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.utils import new_id, utcnow
from app.models.messaging import Conversation, Message
from app.models.user import User
from app.schemas.messaging import MessageCreate
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)


def _participants_list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            return []
    return []


def participant_key(user_a: str, user_b: str, property_id: Optional[str] = None) -> str:
    parts = sorted([user_a, user_b])
    prop = property_id or "_"
    return f"{parts[0]}|{parts[1]}|{prop}"


def _user_conversation_filter(user_id: str):
    """Database-level filter: participant_key encodes sorted user ids."""
    return or_(
        Conversation.participant_key.like(f"{user_id}|%"),
        Conversation.participant_key.like(f"%|{user_id}|%"),
    )


def serialize_conversation(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "participants": _participants_list(conv.participants),
        "property_id": conv.property_id,
        "last_message": conv.last_message,
        "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "receiver_id": msg.receiver_id,
        "message": msg.message,
        "attachment_url": msg.attachment_url,
        "read": msg.read,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def user_in_conversation(conv: Conversation, user_id: str) -> bool:
    return user_id in _participants_list(conv.participants)


async def list_conversations(
    db: AsyncSession, user: UserOut, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    base = select(Conversation).where(_user_conversation_filter(user.id))
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    result = await db.execute(
        base.order_by(
            desc(Conversation.last_message_at),
            desc(Conversation.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_conversation(c) for c in result.scalars().all()], total


async def get_conversation_or_404(db: AsyncSession, conversation_id: str) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Conversation not found")
    return conv


async def assert_conversation_access(
    db: AsyncSession, conversation_id: str, user: UserOut
) -> Conversation:
    conv = await get_conversation_or_404(db, conversation_id)
    if not user_in_conversation(conv, user.id):
        raise ForbiddenError("Not authorized to access this conversation")
    return conv


async def list_messages(
    db: AsyncSession,
    user: UserOut,
    conversation_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    await assert_conversation_access(db, conversation_id, user)
    base = select(Message).where(Message.conversation_id == conversation_id)
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    result = await db.execute(
        base.order_by(asc(Message.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_message(m) for m in result.scalars().all()], total


async def send_message(
    db: AsyncSession,
    user: UserOut,
    data: MessageCreate,
) -> tuple[dict, dict]:
    if data.receiver_id == user.id:
        raise ForbiddenError("Cannot message yourself")

    receiver = await db.execute(select(User).where(User.id == data.receiver_id))
    if not receiver.scalar_one_or_none():
        raise NotFoundError("Recipient not found")

    key = participant_key(user.id, data.receiver_id, data.property_id)
    result = await db.execute(
        select(Conversation).where(Conversation.participant_key == key)
    )
    conversation = result.scalar_one_or_none()

    now = utcnow()
    if not conversation:
        conversation = Conversation(
            id=new_id("conv"),
            participants=sorted([user.id, data.receiver_id]),
            participant_key=key,
            property_id=data.property_id,
            last_message=data.message,
            last_message_at=now,
            created_at=now,
        )
        db.add(conversation)
        await db.flush()
    else:
        if not user_in_conversation(conversation, user.id):
            raise ForbiddenError("Not authorized")
        conversation.last_message = data.message
        conversation.last_message_at = now

    message = Message(
        id=new_id("msg"),
        conversation_id=conversation.id,
        sender_id=user.id,
        receiver_id=data.receiver_id,
        message=data.message,
        attachment_url=None,
        read=False,
        created_at=now,
    )
    db.add(message)
    await db.flush()

    return serialize_message(message), {
        "id": message.id,
        "conversation_id": conversation.id,
    }


async def mark_read(db: AsyncSession, user: UserOut, message_id: str) -> dict:
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise NotFoundError("Message not found")
    if message.receiver_id != user.id:
        raise ForbiddenError("Not authorized")
    message.read = True
    await db.flush()
    return {"message": "Message marked as read"}
