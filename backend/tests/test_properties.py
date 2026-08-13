"""Property CRUD, ownership, archive, and search tests."""
from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_and_list_property(client, owner):
    create = await client.post(
        "/api/properties",
        headers=auth_header(owner),
        json={
            "title": "Lake House Retreat",
            "description": "Beautiful lake house with modern amenities and views.",
            "address": "9 Lake Rd",
            "price": 750000,
            "property_type": "house",
            "area_sqft": 2000,
            "bedrooms": 4,
            "bathrooms": 3,
            "latitude": 41.0,
            "longitude": -73.0,
            "amenities": ["dock", "garage"],
        },
    )
    assert create.status_code == 200
    prop_id = create.json()["id"]

    listed = await client.get("/api/properties", headers=auth_header(owner))
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(p["id"] == prop_id for p in listed.json()["properties"])


@pytest.mark.asyncio
async def test_property_update_ownership(client, owner, buyer, published_property):
    res = await client.put(
        f"/api/properties/{published_property.id}",
        headers=auth_header(buyer),
        json={
            "title": "Hacked Title Value",
            "description": "Should not be allowed to update this listing at all.",
            "address": published_property.address,
            "price": 1,
            "property_type": "apartment",
            "area_sqft": 100,
            "bedrooms": 1,
            "bathrooms": 1,
            "latitude": 1,
            "longitude": 1,
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_archive_preserves_history(
    client, owner, buyer, published_property, tomorrow_iso
):
    booked = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "9:00 AM",
        },
    )
    assert booked.status_code == 200
    booking_id = booked.json()["id"]

    res = await client.delete(
        f"/api/properties/{published_property.id}",
        headers=auth_header(owner),
    )
    assert res.status_code == 200
    assert res.json().get("preserved_bookings", 0) >= 1

    get_res = await client.get(
        f"/api/properties/{published_property.id}",
        headers=auth_header(owner),
    )
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "archived"

    listings = await client.get("/api/bookings", headers=auth_header(buyer))
    assert listings.status_code == 200
    assert any(b["id"] == booking_id for b in listings.json()["bookings"])


@pytest.mark.asyncio
async def test_archived_property_rejects_new_bookings(
    client, owner, buyer, published_property, tomorrow_iso
):
    archived = await client.delete(
        f"/api/properties/{published_property.id}",
        headers=auth_header(owner),
    )
    assert archived.status_code == 200

    booking = await client.post(
        "/api/bookings",
        headers=auth_header(buyer),
        json={
            "property_id": published_property.id,
            "booking_date": tomorrow_iso,
            "time_slot": "10:00 AM",
        },
    )
    assert booking.status_code in (400, 404)


@pytest.mark.asyncio
async def test_search_filters(client, buyer, published_property):
    res = await client.post(
        "/api/properties/search",
        headers=auth_header(buyer),
        json={
            "min_price": 100000,
            "max_price": 600000,
            "property_type": "apartment",
            "bedrooms": 2,
            "page": 1,
            "page_size": 10,
        },
    )
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()["properties"]]
    assert published_property.id in ids
    assert "total" in res.json()
    assert "has_next" in res.json()


@pytest.mark.asyncio
async def test_validation_rejects_negative_price(client, owner):
    res = await client.post(
        "/api/properties",
        headers=auth_header(owner),
        json={
            "title": "Bad Price Listing",
            "description": "This should fail validation because price is invalid.",
            "address": "1 Bad Rd",
            "price": -5,
            "property_type": "house",
            "area_sqft": 1000,
            "bedrooms": 2,
            "bathrooms": 1,
            "latitude": 1,
            "longitude": 1,
        },
    )
    assert res.status_code == 422
