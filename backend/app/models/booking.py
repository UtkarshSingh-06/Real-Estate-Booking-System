"""Booking model with slot uniqueness for active holds."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import BookingStatus, PaymentStatus
from app.core.utils import utcnow
from app.db.base import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("slot_key", name="uq_bookings_slot_key"),
        Index("ix_bookings_property_date_status", "property_id", "booking_date", "status"),
        Index("ix_bookings_user_status", "user_id", "status"),
        Index("ix_bookings_owner_status", "owner_id", "status"),
        Index("ix_bookings_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    property_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_slot: Mapped[str] = mapped_column(String(50), nullable=False)
    # Unique while holding a slot; set to NULL when cancelled/rejected/expired to free the slot
    slot_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(
        String(30), default=BookingStatus.REQUESTED.value, nullable=False, index=True
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.PENDING.value, nullable=False
    )
    deposit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    property = relationship("Property", back_populates="bookings")
    user = relationship("User", foreign_keys=[user_id], back_populates="bookings")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owner_bookings")
