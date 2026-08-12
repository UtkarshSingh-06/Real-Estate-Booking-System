"""Booking engine with availability checks, slot locking, and state machine."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import (
    ALLOWED_BOOKING_TRANSITIONS,
    SLOT_HOLDING_STATUSES,
    BookingStatus,
    PaymentStatus,
    PropertyStatus,
    UserRole,
)
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.utils import ensure_utc, make_slot_key, new_id, to_date, utcnow
from app.models.booking import Booking
from app.models.property import Property
from app.services.deposit import calculate_deposit
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)


def serialize_booking(booking: Booking) -> dict:
    return {
        "id": booking.id,
        "property_id": booking.property_id,
        "user_id": booking.user_id,
        "owner_id": booking.owner_id,
        "booking_date": booking.booking_date.isoformat() if booking.booking_date else None,
        "time_slot": booking.time_slot,
        "status": booking.status,
        "payment_status": booking.payment_status,
        "deposit_amount": booking.deposit_amount,
        "expires_at": booking.expires_at.isoformat() if booking.expires_at else None,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
    }


def _parse_booking_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError("Invalid booking_date format", status_code=422) from exc
    return ensure_utc(dt)


async def expire_stale_bookings(db: AsyncSession) -> int:
    """Release slots held by abandoned REQUESTED / PAYMENT_PENDING bookings."""
    now = utcnow()
    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.status.in_(
                    [
                        BookingStatus.REQUESTED.value,
                        BookingStatus.APPROVED.value,
                        BookingStatus.PAYMENT_PENDING.value,
                        "pending",
                    ]
                ),
                Booking.expires_at.is_not(None),
                Booking.expires_at < now,
            )
        )
    )
    expired = list(result.scalars().all())
    for booking in expired:
        booking.status = BookingStatus.EXPIRED.value
        booking.slot_key = None
        booking.updated_at = now
        if booking.payment_status == PaymentStatus.PENDING.value:
            booking.payment_status = PaymentStatus.EXPIRED.value
    if expired:
        await db.flush()
    return len(expired)


async def create_booking(db: AsyncSession, user: UserOut, data: BookingCreate) -> dict:
    settings = get_settings()
    await expire_stale_bookings(db)

    # Lock property row to serialize concurrent booking attempts for the same listing
    result = await db.execute(
        select(Property)
        .where(Property.id == data.property_id, Property.deleted_at.is_(None))
        .with_for_update()
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise NotFoundError("Property not found")
    if prop.status != PropertyStatus.PUBLISHED.value:
        raise AppError("Property is not available for booking", status_code=400)
    if prop.owner_id == user.id:
        raise AppError("You cannot book your own property", status_code=400)

    booking_date = _parse_booking_datetime(data.booking_date)
    if booking_date.date() < utcnow().date():
        raise AppError("Booking date cannot be in the past", status_code=400)

    slot_key = make_slot_key(prop.id, booking_date, data.time_slot)

    conflict = await db.execute(
        select(Booking).where(
            and_(
                Booking.slot_key == slot_key,
                Booking.status.in_(list(SLOT_HOLDING_STATUSES)),
            )
        )
    )
    if conflict.scalar_one_or_none():
        raise ConflictError("This time slot is already booked")

    deposit = calculate_deposit(prop.price, settings)

    expires_at = utcnow() + timedelta(hours=settings.booking_request_expire_hours)
    booking = Booking(
        id=new_id("book"),
        property_id=prop.id,
        user_id=user.id,
        owner_id=prop.owner_id,
        booking_date=booking_date,
        time_slot=data.time_slot,
        slot_key=slot_key,
        status=BookingStatus.REQUESTED.value,
        payment_status=PaymentStatus.PENDING.value,
        deposit_amount=deposit,
        expires_at=expires_at,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(booking)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("This time slot is already booked") from exc

    return {
        "id": booking.id,
        "message": "Booking request created",
        "status": booking.status,
        "deposit_amount": booking.deposit_amount,
        "deposit_policy": f"{int(settings.default_deposit_percent * 100)}% of listing price",
    }


async def list_user_bookings(
    db: AsyncSession, user: UserOut, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    await expire_stale_bookings(db)
    base = select(Booking).where(Booking.user_id == user.id)
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    result = await db.execute(
        base.order_by(Booking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_booking(b) for b in result.scalars().all()], total


async def list_owner_bookings(
    db: AsyncSession, user: UserOut, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    if user.role not in (
        UserRole.OWNER.value,
        UserRole.AGENT.value,
        UserRole.ADMIN.value,
    ):
        raise ForbiddenError("Not authorized")
    await expire_stale_bookings(db)
    base = select(Booking).where(Booking.owner_id == user.id)
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    result = await db.execute(
        base.order_by(Booking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_booking(b) for b in result.scalars().all()], total


def _assert_transition(current: str, new_status: str) -> None:
    allowed = ALLOWED_BOOKING_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise AppError(
            f"Cannot transition booking from '{current}' to '{new_status}'",
            status_code=400,
            code="invalid_transition",
        )


async def transition_booking(
    db: AsyncSession,
    user: UserOut,
    booking_id: str,
    new_status: str,
    *,
    actor: str = "user",
) -> dict:
    """Apply a validated booking state transition with authorization."""
    await expire_stale_bookings(db)
    settings = get_settings()

    result = await db.execute(
        select(Booking).where(Booking.id == booking_id).with_for_update()
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")

    new_status = (
        new_status.value if hasattr(new_status, "value") else str(new_status)
    ).lower()

    # Normalize legacy frontend values
    legacy_map = {"confirmed": BookingStatus.APPROVED.value}
    if new_status == "confirmed" and booking.status in (
        BookingStatus.REQUESTED.value,
        "pending",
    ):
        # Owner "confirm" means approve for payment
        new_status = BookingStatus.APPROVED.value

    is_owner = booking.owner_id == user.id or user.role == UserRole.ADMIN.value
    is_buyer = booking.user_id == user.id

    if new_status == BookingStatus.CANCELLED.value:
        if not (is_owner or is_buyer):
            raise ForbiddenError("Not authorized")
    elif new_status in (
        BookingStatus.APPROVED.value,
        BookingStatus.REJECTED.value,
    ):
        if not is_owner:
            raise ForbiddenError("Only the property owner can approve or reject")
    elif new_status == BookingStatus.PAYMENT_PENDING.value:
        if not is_buyer and actor != "system":
            raise ForbiddenError("Not authorized")
    elif new_status == BookingStatus.CONFIRMED.value:
        if actor != "system" and user.role != UserRole.ADMIN.value:
            raise ForbiddenError("Booking confirmation requires payment")
    else:
        if not is_owner and user.role != UserRole.ADMIN.value:
            raise ForbiddenError("Not authorized")

    _assert_transition(booking.status, new_status)

    booking.status = new_status
    booking.updated_at = utcnow()

    if new_status in (
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    ):
        booking.slot_key = None
    elif new_status == BookingStatus.APPROVED.value:
        booking.status = BookingStatus.PAYMENT_PENDING.value
        booking.expires_at = utcnow() + timedelta(hours=settings.booking_payment_expire_hours)
    elif new_status == BookingStatus.PAYMENT_PENDING.value:
        booking.expires_at = utcnow() + timedelta(hours=settings.booking_payment_expire_hours)

    await db.flush()
    return {"message": f"Booking {booking.status}", "status": booking.status}


async def mark_booking_confirmed_paid(db: AsyncSession, booking: Booking) -> None:
    """Idempotent transition used by payment webhook processing."""
    if booking.payment_status == PaymentStatus.PAID.value and booking.status == BookingStatus.CONFIRMED.value:
        return

    if booking.status in (
        BookingStatus.CANCELLED.value,
        BookingStatus.REJECTED.value,
        BookingStatus.EXPIRED.value,
    ):
        logger.warning(
            "Payment received for terminal booking %s (status=%s)",
            booking.id,
            booking.status,
        )
        booking.payment_status = PaymentStatus.PAID.value
        booking.updated_at = utcnow()
        return

    booking.payment_status = PaymentStatus.PAID.value
    booking.status = BookingStatus.CONFIRMED.value
    booking.expires_at = None
    booking.updated_at = utcnow()
    await db.flush()
