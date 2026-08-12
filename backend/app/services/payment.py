"""Stripe payment service — webhooks are the source of truth for paid state."""
from __future__ import annotations

import logging
from typing import Any, Optional

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import (
    BookingStatus,
    PaymentStatus,
    PaymentTransactionStatus,
)
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.utils import new_id, utcnow
from app.models.booking import Booking
from app.models.payment import PaymentTransaction, ProcessedWebhookEvent
from app.schemas.user import UserOut
from app.services.booking import mark_booking_confirmed_paid

logger = logging.getLogger(__name__)

# Only bookings awaiting buyer payment may start/resume checkout.
CHECKOUT_ELIGIBLE_STATUSES = {
    BookingStatus.PAYMENT_PENDING.value,
}


def _configure_stripe() -> None:
    settings = get_settings()
    if not settings.stripe_api_key:
        raise AppError("Stripe not configured", status_code=503, code="stripe_unconfigured")
    stripe.api_key = settings.stripe_api_key


async def _get_pending_checkout(
    db: AsyncSession, booking_id: str, user_id: str
) -> PaymentTransaction | None:
    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.booking_id == booking_id,
            PaymentTransaction.user_id == user_id,
            PaymentTransaction.payment_status == PaymentStatus.PENDING.value,
            PaymentTransaction.status == PaymentTransactionStatus.PENDING.value,
        )
    )
    return result.scalar_one_or_none()


async def create_checkout(
    db: AsyncSession,
    user: UserOut,
    booking_id: str,
    origin_url: str,
) -> dict:
    _configure_stripe()

    result = await db.execute(
        select(Booking).where(Booking.id == booking_id).with_for_update()
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")
    if booking.user_id != user.id:
        raise ForbiddenError("Not authorized")

    if booking.status in (
        BookingStatus.REQUESTED.value,
        "pending",
        BookingStatus.APPROVED.value,
    ):
        raise AppError(
            "Booking must be approved by the owner before payment",
            status_code=400,
            code="approval_required",
        )
    if booking.status in (
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    ):
        raise AppError(
            f"Cannot pay for booking in '{booking.status}' status",
            status_code=400,
        )
    if booking.status == BookingStatus.CONFIRMED.value:
        raise AppError("Booking is already confirmed", status_code=400)
    if booking.status not in CHECKOUT_ELIGIBLE_STATUSES:
        raise AppError(
            f"Booking status '{booking.status}' does not allow payment",
            status_code=400,
        )
    if booking.payment_status == PaymentStatus.PAID.value:
        raise AppError("Booking is already paid", status_code=400)

    # Resume an open checkout session when one already exists.
    existing_txn = await _get_pending_checkout(db, booking_id, user.id)
    if existing_txn:
        try:
            session = stripe.checkout.Session.retrieve(existing_txn.session_id)
            if session.status == "open" and session.url:
                return {"url": session.url, "session_id": session.id}
        except stripe.StripeError as exc:
            logger.warning("Could not resume session %s: %s", existing_txn.session_id, exc)

    success_url = f"{origin_url.rstrip('/')}/booking-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url.rstrip('/')}/bookings"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Property Viewing Deposit - {booking_id}",
                        },
                        "unit_amount": int(round(booking.deposit_amount * 100)),
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=booking_id,
            metadata={
                "booking_id": booking_id,
                "user_id": user.id,
            },
        )
    except stripe.StripeError as exc:
        logger.error("Stripe checkout error: %s", exc)
        raise AppError("Error creating checkout session", status_code=502) from exc

    txn = PaymentTransaction(
        id=new_id("txn"),
        session_id=checkout_session.id,
        booking_id=booking_id,
        user_id=user.id,
        amount=booking.deposit_amount,
        currency="usd",
        status=PaymentTransactionStatus.PENDING.value,
        payment_status=PaymentStatus.PENDING.value,
        extra_metadata={"booking_id": booking_id},
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(txn)
    await db.flush()

    return {"url": checkout_session.url, "session_id": checkout_session.id}


async def _apply_paid_session(db: AsyncSession, session_id: str, session_obj: Any) -> None:
    result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.session_id == session_id)
        .with_for_update()
    )
    txn = result.scalar_one_or_none()
    if not txn:
        logger.warning("No payment transaction for session %s", session_id)
        return

    if txn.payment_status == PaymentStatus.PAID.value:
        return

    txn.payment_status = PaymentStatus.PAID.value
    txn.status = PaymentTransactionStatus.COMPLETED.value
    txn.updated_at = utcnow()

    booking_result = await db.execute(
        select(Booking).where(Booking.id == txn.booking_id).with_for_update()
    )
    booking = booking_result.scalar_one_or_none()
    if booking:
        await mark_booking_confirmed_paid(db, booking)
    await db.flush()


async def _process_webhook_event(db: AsyncSession, event: dict) -> None:
    event_type = event["type"]
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        if session.get("payment_status") == "paid" or session.get("status") == "complete":
            await _apply_paid_session(db, session["id"], session)
    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        result = await db.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.session_id == session["id"]
            )
        )
        txn = result.scalar_one_or_none()
        if txn and txn.payment_status == PaymentStatus.PENDING.value:
            txn.payment_status = PaymentStatus.EXPIRED.value
            txn.status = PaymentTransactionStatus.EXPIRED.value
            txn.updated_at = utcnow()
            booking_result = await db.execute(
                select(Booking).where(Booking.id == txn.booking_id).with_for_update()
            )
            booking = booking_result.scalar_one_or_none()
            if booking and booking.status == BookingStatus.PAYMENT_PENDING.value:
                booking.status = BookingStatus.EXPIRED.value
                booking.payment_status = PaymentStatus.EXPIRED.value
                booking.slot_key = None
                booking.updated_at = utcnow()
    elif event_type in ("charge.refunded", "refund.created"):
        obj = event["data"]["object"]
        session_id = None
        if isinstance(obj, dict):
            session_id = obj.get("metadata", {}).get("checkout_session_id")
        if session_id:
            result = await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.session_id == session_id)
            )
            txn = result.scalar_one_or_none()
            if txn:
                txn.payment_status = PaymentStatus.REFUNDED.value
                txn.status = PaymentTransactionStatus.REFUNDED.value
                txn.updated_at = utcnow()
                booking_result = await db.execute(
                    select(Booking).where(Booking.id == txn.booking_id)
                )
                booking = booking_result.scalar_one_or_none()
                if booking:
                    booking.payment_status = PaymentStatus.REFUNDED.value
                    booking.updated_at = utcnow()


async def get_payment_status(
    db: AsyncSession,
    user: UserOut,
    session_id: str,
) -> dict:
    """Read-only status check. Does NOT mutate booking/payment state."""
    _configure_stripe()

    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.session_id == session_id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise NotFoundError("Payment session not found")
    if txn.user_id != user.id and user.role != "admin":
        raise ForbiddenError("Not authorized")

    booking_status = None
    booking_result = await db.execute(select(Booking).where(Booking.id == txn.booking_id))
    booking = booking_result.scalar_one_or_none()
    if booking:
        booking_status = booking.status

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        return {
            "session_id": checkout_session.id,
            "payment_status": checkout_session.payment_status,
            "status": checkout_session.status,
            "booking_id": txn.booking_id,
            "booking_status": booking_status,
            "local_payment_status": txn.payment_status,
        }
    except stripe.StripeError as exc:
        logger.error("Stripe status error: %s", exc)
        return {
            "session_id": session_id,
            "payment_status": txn.payment_status,
            "status": txn.status,
            "booking_id": txn.booking_id,
            "booking_status": booking_status,
            "local_payment_status": txn.payment_status,
        }


async def handle_stripe_webhook(
    db: AsyncSession,
    payload: bytes,
    signature: Optional[str],
) -> dict:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        logger.warning("Stripe webhook secret not configured")
        raise AppError("Webhook not configured", status_code=503)

    _configure_stripe()

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except ValueError as exc:
        raise AppError("Invalid payload", status_code=400) from exc
    except stripe.SignatureVerificationError as exc:
        raise AppError("Invalid signature", status_code=400) from exc

    event_id = event["id"]
    event_type = event["type"]

    existing = await db.execute(
        select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event_id)
    )
    if existing.scalar_one_or_none():
        return {"received": True, "duplicate": True}

    # Claim the event idempotency key first so concurrent deliveries cannot
    # both execute payment state transitions.
    db.add(
        ProcessedWebhookEvent(
            id=new_id("evt"),
            event_id=event_id,
            event_type=event_type,
            processed_at=utcnow(),
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("Duplicate concurrent webhook %s", event_id)
        return {"received": True, "duplicate": True}

    await _process_webhook_event(db, event)

    logger.info("Processed Stripe webhook %s (%s)", event_id, event_type)
    return {"received": True, "duplicate": False}
