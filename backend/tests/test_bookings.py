"""Booking availability, conflicts, and state transitions."""
from __future__ import annotations

import asyncio

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_booking_requires_property_id(client, buyer, tomorrow_iso):
    res = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "booking_date": tomorrow_iso,
            "time_slot": "10:00 AM",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_booking_success(client, buyer, published_property, tomorrow_iso):
    res = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "10:00 AM",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "requested"
    assert body["deposit_amount"] == 50_000.0


@pytest.mark.asyncio
async def test_duplicate_slot_conflict(
    client, buyer, other_buyer, published_property, tomorrow_iso
):
    payload = {
        "property_id": published_property.id,
        "booking_date": tomorrow_iso,
        "time_slot": "11:00 AM",
    }
    first = await client.post("/api/bookings", headers=auth_header(buyer), json=payload)
    assert first.status_code == 200
    second = await client.post(
        "/api/bookings", headers=auth_header(other_buyer), json=payload
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_cannot_book_own_property(client, owner, published_property, tomorrow_iso):
    res = await client.post(
        "/api/bookings",
        headers=auth_header(owner),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "1:00 PM",
        },
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_owner_approve_transition(
    client, buyer, owner, published_property, tomorrow_iso
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

    # Buyer cannot approve
    forbidden = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(buyer),
        params={"status": "approved"},
    )
    assert forbidden.status_code == 403

    approved = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(owner),
        params={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "payment_pending"


@pytest.mark.asyncio
async def test_invalid_time_slot(client, buyer, published_property, tomorrow_iso):
    res = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "3:30 AM",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_cancel_frees_slot(
    client, buyer, other_buyer, owner, published_property, tomorrow_iso
):
    payload = {
        "property_id": published_property.id,
        "booking_date": tomorrow_iso,
        "time_slot": "3:00 PM",
    }
    created = await client.post("/api/bookings", headers=auth_header(buyer), json=payload)
    booking_id = created.json()["id"]
    cancel = await client.put(
        f"/api/bookings/{booking_id}/status",
        headers=auth_header(buyer),
        params={"status": "cancelled"},
    )
    assert cancel.status_code == 200

    rebook = await client.post(
        "/api/bookings", headers=auth_header(other_buyer), json=payload
    )
    assert rebook.status_code == 200
