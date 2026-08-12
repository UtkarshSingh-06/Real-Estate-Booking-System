"""Booking schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import BookingStatus, PaymentStatus
from app.schemas.common import ORMModel

ALLOWED_TIME_SLOTS = {
    "9:00 AM",
    "10:00 AM",
    "11:00 AM",
    "12:00 PM",
    "1:00 PM",
    "2:00 PM",
    "3:00 PM",
    "4:00 PM",
    "5:00 PM",
}


class BookingCreate(BaseModel):
    model_config = {"extra": "ignore"}

    property_id: str = Field(..., min_length=3, max_length=64)
    booking_date: str = Field(..., min_length=8, max_length=40)
    time_slot: str = Field(..., min_length=3, max_length=50)

    @field_validator("time_slot")
    @classmethod
    def validate_time_slot(cls, value: str) -> str:
        value = value.strip()
        if value not in ALLOWED_TIME_SLOTS:
            raise ValueError(
                f"Invalid time slot. Allowed: {', '.join(sorted(ALLOWED_TIME_SLOTS))}"
            )
        return value


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class BookingOut(ORMModel):
    id: str
    property_id: str
    user_id: str
    owner_id: str
    booking_date: datetime
    time_slot: str
    status: str
    payment_status: str
    deposit_amount: float
    expires_at: Optional[datetime] = None
    created_at: datetime
