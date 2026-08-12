"""Payment webhook idempotency and read-only status checks."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.enums import BookingStatus, PaymentStatus
from app.core.utils import new_id, utcnow
from app.models.booking import Booking
from app.models.payment import PaymentTransaction
from app.services.payment import handle_stripe_webhook, _apply_paid_session
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_payment_status_requires_auth(client):
    res = await client.get("/api/payments/status/cs_test_123")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_payment_status_does_not_mutate(
    client, db_session, buyer, owner, published_property, tomorrow_iso
):
    booking = Booking(
        id=new_id("book"),
        property_id=published_property.id,
        user_id=buyer.id,
        owner_id=owner.id,
        booking_date=utcnow(),
        time_slot="10:00 AM",
        slot_key=f"{published_property.id}|slot-status",
        status=BookingStatus.PAYMENT_PENDING.value,
        payment_status=PaymentStatus.PENDING.value,
        deposit_amount=1000,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    txn = PaymentTransaction(
        id=new_id("txn"),
        session_id="cs_test_readonly",
        booking_id=booking.id,
        user_id=buyer.id,
        amount=1000,
        currency="usd",
        status="pending",
        payment_status="pending",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add_all([booking, txn])
    await db_session.commit()

    mock_session = MagicMock()
    mock_session.id = "cs_test_readonly"
    mock_session.payment_status = "paid"
    mock_session.status = "complete"

    with patch("app.services.payment.stripe.checkout.Session.retrieve", return_value=mock_session):
        with patch("app.services.payment._configure_stripe"):
            res = await client.get(
                "/api/payments/status/cs_test_readonly",
                headers=auth_header(buyer),
            )
    assert res.status_code == 200

    await db_session.refresh(booking)
    assert booking.status == BookingStatus.PAYMENT_PENDING.value
    assert booking.payment_status == PaymentStatus.PENDING.value


@pytest.mark.asyncio
async def test_webhook_idempotent_paid(db_session, buyer, owner, published_property):
    booking = Booking(
        id=new_id("book"),
        property_id=published_property.id,
        user_id=buyer.id,
        owner_id=owner.id,
        booking_date=utcnow(),
        time_slot="4:00 PM",
        slot_key=f"{published_property.id}|slot-pay",
        status=BookingStatus.PAYMENT_PENDING.value,
        payment_status=PaymentStatus.PENDING.value,
        deposit_amount=1000,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    txn = PaymentTransaction(
        id=new_id("txn"),
        session_id="cs_test_pay",
        booking_id=booking.id,
        user_id=buyer.id,
        amount=1000,
        currency="usd",
        status="pending",
        payment_status="pending",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add_all([booking, txn])
    await db_session.commit()

    event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_pay",
                "payment_status": "paid",
                "status": "complete",
            }
        },
    }

    with patch("app.services.payment.stripe.Webhook.construct_event", return_value=event):
        with patch("app.services.payment._configure_stripe"):
            first = await handle_stripe_webhook(db_session, b"{}", "sig")
            second = await handle_stripe_webhook(db_session, b"{}", "sig")

    assert first["received"] is True
    assert first["duplicate"] is False
    assert second["duplicate"] is True

    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED.value
    assert booking.payment_status == PaymentStatus.PAID.value


@pytest.mark.asyncio
async def test_webhook_concurrent_duplicate_delivery(engine, buyer, owner, published_property):
    """Two simultaneous webhook deliveries must not double-apply payment state."""
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as setup:
        booking = Booking(
            id=new_id("book"),
            property_id=published_property.id,
            user_id=buyer.id,
            owner_id=owner.id,
            booking_date=utcnow(),
            time_slot="5:00 PM",
            slot_key=f"{published_property.id}|slot-concurrent",
            status=BookingStatus.PAYMENT_PENDING.value,
            payment_status=PaymentStatus.PENDING.value,
            deposit_amount=1000,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        txn = PaymentTransaction(
            id=new_id("txn"),
            session_id="cs_test_concurrent",
            booking_id=booking.id,
            user_id=buyer.id,
            amount=1000,
            currency="usd",
            status="pending",
            payment_status="pending",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        setup.add_all([booking, txn])
        await setup.commit()
        booking_id = booking.id

    event = {
        "id": "evt_concurrent_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_concurrent",
                "payment_status": "paid",
                "status": "complete",
            }
        },
    }

    async def deliver():
        async with Session() as session:
            with patch("app.services.payment.stripe.Webhook.construct_event", return_value=event):
                with patch("app.services.payment._configure_stripe"):
                    result = await handle_stripe_webhook(session, b"{}", "sig")
                    await session.commit()
                    return result

    results = await asyncio.gather(deliver(), deliver(), return_exceptions=True)
    dict_results = [r for r in results if isinstance(r, dict)]
    assert dict_results, f"expected webhook handlers to return results, got {results!r}"
    assert all(r.get("received") for r in dict_results)
    assert sum(1 for r in dict_results if r.get("duplicate")) == 1
    assert sum(1 for r in dict_results if not r.get("duplicate")) == 1

    async with Session() as verify:
        refreshed = await verify.get(Booking, booking_id)
        assert refreshed.status == BookingStatus.CONFIRMED.value
        assert refreshed.payment_status == PaymentStatus.PAID.value


@pytest.mark.asyncio
async def test_webhook_invalid_signature(db_session):
    import stripe

    from app.core.exceptions import AppError

    with patch(
        "app.services.payment.stripe.Webhook.construct_event",
        side_effect=stripe.SignatureVerificationError("bad", "sig"),
    ):
        with patch("app.services.payment._configure_stripe"):
            with pytest.raises(AppError) as exc:
                await handle_stripe_webhook(db_session, b"{}", "sig")
            assert exc.value.status_code == 400
