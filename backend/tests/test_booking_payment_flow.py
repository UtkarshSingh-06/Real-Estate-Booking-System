"""Booking deposit authority and payment workflow tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_deposit_ignores_malicious_client_value(
    client, buyer, published_property, tomorrow_iso
):
    """Client-supplied deposit_amount must not override server calculation."""
    res = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "10:00 AM",
            "deposit_amount": 1,
        },
    )
    assert res.status_code == 200
    body = res.json()
    # 10% of 500_000 listing price
    assert body["deposit_amount"] == 50_000.0


@pytest.mark.asyncio
async def test_checkout_rejected_before_owner_approval(
    client, buyer, published_property, tomorrow_iso
):
    created = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "12:00 PM",
        },
    )
    booking_id = created.json()["id"]

    with patch("app.services.payment._configure_stripe"):
        checkout = await client.post(
            "/api/payments/create-checkout",
            headers=auth_header(buyer),
            json={"booking_id": booking_id, "origin_url": "http://localhost:3000"},
        )
    assert checkout.status_code == 400
    assert "approved" in checkout.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checkout_allowed_after_owner_approval(
    client, buyer, owner, published_property, tomorrow_iso
):
    created = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "1:00 PM",
        },
    )
    booking_id = created.json()["id"]

    approved = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(owner),
        params={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "payment_pending"

    mock_session = MagicMock()
    mock_session.id = "cs_test_checkout"
    mock_session.url = "https://checkout.stripe.test/session"
    mock_session.status = "open"

    with patch("app.services.payment.stripe.checkout.Session.create", return_value=mock_session):
        with patch("app.services.payment._configure_stripe"):
            checkout = await client.post(
                "/api/payments/create-checkout",
                headers=auth_header(buyer),
                json={"booking_id": booking_id, "origin_url": "http://localhost:3000"},
            )
    assert checkout.status_code == 200
    assert checkout.json()["session_id"] == "cs_test_checkout"


@pytest.mark.asyncio
async def test_checkout_rejected_for_cancelled_booking(
    client, buyer, published_property, tomorrow_iso
):
    created = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "2:00 PM",
        },
    )
    booking_id = created.json()["id"]
    await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(buyer),
        params={"status": "cancelled"},
    )
    with patch("app.services.payment._configure_stripe"):
        checkout = await client.post(
            "/api/payments/create-checkout",
            headers=auth_header(buyer),
            json={"booking_id": booking_id, "origin_url": "http://localhost:3000"},
        )
    assert checkout.status_code == 400


@pytest.mark.asyncio
async def test_checkout_rejected_for_rejected_booking(
    client, buyer, owner, published_property, tomorrow_iso
):
    created = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "3:00 PM",
        },
    )
    booking_id = created.json()["id"]
    rejected = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(owner),
        params={"status": "rejected"},
    )
    assert rejected.status_code == 200
    with patch("app.services.payment._configure_stripe"):
        checkout = await client.post(
            "/api/payments/create-checkout",
            headers=auth_header(buyer),
            json={"booking_id": booking_id, "origin_url": "http://localhost:3000"},
        )
    assert checkout.status_code == 400


@pytest.mark.asyncio
async def test_checkout_rejected_for_confirmed_booking(
    client, db_session, buyer, owner, published_property
):
    from app.core.enums import BookingStatus, PaymentStatus
    from app.core.utils import new_id, utcnow
    from app.models.booking import Booking

    booking = Booking(
        id=new_id("book"),
        property_id=published_property.id,
        user_id=buyer.id,
        owner_id=owner.id,
        booking_date=utcnow(),
        time_slot="4:00 PM",
        slot_key=f"{published_property.id}|confirmed-slot",
        status=BookingStatus.CONFIRMED.value,
        payment_status=PaymentStatus.PAID.value,
        deposit_amount=50_000,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db_session.add(booking)
    await db_session.commit()

    with patch("app.services.payment._configure_stripe"):
        checkout = await client.post(
            "/api/payments/create-checkout",
            headers=auth_header(buyer),
            json={"booking_id": booking.id, "origin_url": "http://localhost:3000"},
        )
    assert checkout.status_code == 400


@pytest.mark.asyncio
async def test_checkout_uses_server_calculated_deposit_amount(
    client, buyer, owner, published_property, tomorrow_iso
):
    """Stripe unit_amount must come from stored booking.deposit_amount, not the client."""
    created = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "5:00 PM",
            "deposit_amount": 1,
        },
    )
    assert created.status_code == 200
    assert created.json()["deposit_amount"] == 50_000.0
    booking_id = created.json()["id"]

    approved = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(owner),
        params={"status": "approved"},
    )
    assert approved.json()["status"] == "payment_pending"

    mock_session = MagicMock()
    mock_session.id = "cs_test_amount"
    mock_session.url = "https://checkout.stripe.test/amount"
    mock_session.status = "open"
    create_mock = MagicMock(return_value=mock_session)

    with patch("app.services.payment.stripe.checkout.Session.create", create_mock):
        with patch("app.services.payment._configure_stripe"):
            checkout = await client.post(
                "/api/payments/create-checkout",
                headers=auth_header(buyer),
                json={"booking_id": booking_id, "origin_url": "http://localhost:3000"},
            )
    assert checkout.status_code == 200
    kwargs = create_mock.call_args.kwargs
    unit_amount = kwargs["line_items"][0]["price_data"]["unit_amount"]
    assert unit_amount == 5_000_000  # $50,000.00 in cents
