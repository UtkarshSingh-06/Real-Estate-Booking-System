"""Messaging schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class MessageCreate(BaseModel):
    receiver_id: str = Field(..., min_length=3, max_length=64)
    property_id: Optional[str] = Field(None, max_length=64)
    message: str = Field(..., min_length=1, max_length=5000)
    # Attachments are not supported in v1 — reject if provided
    attachment_url: Optional[str] = Field(None, max_length=500)

    @field_validator("attachment_url")
    @classmethod
    def reject_attachments(cls, value: Optional[str]) -> Optional[str]:
        if value:
            raise ValueError("File attachments are not supported")
        return None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty")
        return value


class MessageOut(ORMModel):
    id: str
    conversation_id: str
    sender_id: str
    receiver_id: str
    message: str
    attachment_url: Optional[str] = None
    read: bool = False
    created_at: datetime


class ConversationOut(ORMModel):
    id: str
    participants: List[str]
    property_id: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime


class MessageSendResponse(BaseModel):
    id: str
    conversation_id: str
