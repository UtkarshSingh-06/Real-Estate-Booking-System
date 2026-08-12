"""Payment schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import ORMModel


class CheckoutCreate(BaseModel):
    booking_id: str = Field(..., min_length=3, max_length=64)
    origin_url: str = Field(..., min_length=8, max_length=500)


class CheckoutResponse(BaseModel):
    url: str
    session_id: str


class PaymentStatusOut(BaseModel):
    session_id: str
    payment_status: str
    status: str
    booking_id: Optional[str] = None
    booking_status: Optional[str] = None


class PaymentTransactionOut(ORMModel):
    id: str
    session_id: str
    booking_id: str
    user_id: str
    amount: float
    currency: str
    status: str
    payment_status: str
    created_at: datetime
