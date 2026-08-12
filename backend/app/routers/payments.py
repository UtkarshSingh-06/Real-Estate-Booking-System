"""Payment and Stripe webhook routes."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.payment import CheckoutCreate
from app.schemas.user import UserOut
from app.services import payment as payment_service

router = APIRouter(tags=["payments"])


@router.post("/payments/create-checkout")
async def create_checkout(
    body: CheckoutCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await payment_service.create_checkout(
        db, user, body.booking_id, body.origin_url
    )


@router.get("/payments/status/{session_id}")
async def payment_status(
    session_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await payment_service.get_payment_status(db, user, session_id)


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    payload = await request.body()
    return await payment_service.handle_stripe_webhook(db, payload, stripe_signature)
