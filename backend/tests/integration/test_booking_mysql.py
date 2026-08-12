"""MySQL booking concurrency integration test."""
from __future__ import annotations

import asyncio
import os

import pytest

from tests.conftest import auth_header, _create_user
from tests.integration.conftest import RUN_MYSQL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not RUN_MYSQL, reason="RUN_MYSQL_TESTS not set"),
]


@pytest.mark.asyncio
async def test_mysql_duplicate_slot_second_booking_rejected(mysql_client, mysql_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from app.models.property import Property
    from app.core.utils import new_id, utcnow

    Session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        owner = await _create_user(db, role="owner", email="mysql-owner@example.com")
        buyer_a = await _create_user(db, role="buyer", email="mysql-buyer-a@example.com")
        buyer_b = await _create_user(db, role="buyer", email="mysql-buyer-b@example.com")
        prop = Property(
            id=new_id("prop"),
            owner_id=owner.id,
            title="MySQL Test Home",
            description="Integration test property for booking concurrency checks.",
            address="1 Test Lane",
            latitude=1.0,
            longitude=2.0,
            price=300_000,
            property_type="house",
            area_sqft=1500,
            bedrooms=3,
            bathrooms=2,
            amenities=[],
            images=[],
            status="published",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(prop)
        await db.commit()
        prop_id = prop.id

    tomorrow = "2030-06-15T10:00:00+00:00"
    payload = {
        "property_id": prop_id,
        "booking_date": tomorrow,
        "time_slot": "10:00 AM",
    }

    async def book_as(user):
        return await mysql_client.post(
            "/api/bookings",
            headers=auth_header(user),
            json=payload,
        )

    first = await book_as(buyer_a)
    assert first.status_code == 200

    second = await book_as(buyer_b)
    assert second.status_code == 409
