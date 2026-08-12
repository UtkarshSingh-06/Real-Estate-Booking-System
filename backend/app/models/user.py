"""User and session models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserRole
from app.core.utils import utcnow
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.BUYER.value, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    properties = relationship("Property", back_populates="owner")
    bookings = relationship("Booking", foreign_keys="Booking.user_id", back_populates="user")
    owner_bookings = relationship(
        "Booking", foreign_keys="Booking.owner_id", back_populates="owner"
    )
    sent_messages = relationship(
        "Message", foreign_keys="Message.sender_id", back_populates="sender"
    )
    received_messages = relationship(
        "Message", foreign_keys="Message.receiver_id", back_populates="receiver"
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
