"""MySQL integration tests for schema, constraints, and booking concurrency."""
from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import BookingStatus, PaymentStatus
from app.core.exceptions import ConflictError
from app.core.utils import make_slot_key, new_id, utcnow
from app.db.base import Base
from app.models.booking import Booking
from app.models.property import Property
from app.schemas.booking import BookingCreate
from app.schemas.user import UserOut
from app.services.booking import create_booking
from tests.conftest import _create_user
from tests.integration.conftest import RUN_MYSQL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not RUN_MYSQL, reason="RUN_MYSQL_TESTS not set"),
]


@pytest.mark.asyncio
async def test_mysql_schema_tables_exist(mysql_engine):
    expected = {
        "users",
        "user_sessions",
        "properties",
        "bookings",
        "conversations",
        "messages",
        "payment_transactions",
        "processed_webhook_events",
    }
    async with mysql_engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        tables = {row[0] for row in result.fetchall()}
    missing = expected - tables
    assert not missing, f"Missing tables after Alembic: {missing}"


@pytest.mark.asyncio
async def test_mysql_slot_key_unique_constraint(mysql_engine):
    Session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        owner = await _create_user(db, role="owner", email="slot-owner@example.com")
        buyer = await _create_user(db, role="buyer", email="slot-buyer@example.com")
        prop = Property(
            id=new_id("prop"),
            owner_id=owner.id,
            title="Constraint Home",
            description="Property used to verify unique slot_key constraint on MySQL.",
            address="2 Constraint Ave",
            latitude=1.0,
            longitude=2.0,
            price=250_000,
            property_type="house",
            area_sqft=1200,
            bedrooms=3,
            bathrooms=2,
            amenities=[],
            images=[],
            status="published",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(prop)
        await db.flush()
        slot = make_slot_key(prop.id, "2030-07-01", "10:00 AM")
        first = Booking(
            id=new_id("book"),
            property_id=prop.id,
            user_id=buyer.id,
            owner_id=owner.id,
            booking_date=utcnow(),
            time_slot="10:00 AM",
            slot_key=slot,
            status=BookingStatus.REQUESTED.value,
            payment_status=PaymentStatus.PENDING.value,
            deposit_amount=25000,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(first)
        await db.commit()

        buyer2 = await _create_user(db, role="buyer", email="slot-buyer-2@example.com")
        duplicate = Booking(
            id=new_id("book"),
            property_id=prop.id,
            user_id=buyer2.id,
            owner_id=owner.id,
            booking_date=utcnow(),
            time_slot="10:00 AM",
            slot_key=slot,
            status=BookingStatus.REQUESTED.value,
            payment_status=PaymentStatus.PENDING.value,
            deposit_amount=25000,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_mysql_duplicate_slot_via_service(mysql_engine):
    Session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        owner = await _create_user(db, role="owner", email="svc-owner@example.com")
        buyer_a = await _create_user(db, role="buyer", email="svc-buyer-a@example.com")
        buyer_b = await _create_user(db, role="buyer", email="svc-buyer-b@example.com")
        prop = Property(
            id=new_id("prop"),
            owner_id=owner.id,
            title="Service Lock Home",
            description="Property used to verify booking service conflict handling on MySQL.",
            address="3 Service Lane",
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
        buyer_a_out = UserOut.model_validate(buyer_a)
        buyer_b_out = UserOut.model_validate(buyer_b)

    payload = BookingCreate(
        property_id=prop_id,
        booking_date="2030-06-15T10:00:00+00:00",
        time_slot="10:00 AM",
    )

    async with Session() as db:
        first = await create_booking(db, buyer_a_out, payload)
        await db.commit()
        assert first["status"] == BookingStatus.REQUESTED.value
        assert first["deposit_amount"] == 30_000.0

    async with Session() as db:
        with pytest.raises(ConflictError):
            await create_booking(db, buyer_b_out, payload)
        await db.rollback()

    async with Session() as db:
        rows = (
            await db.execute(select(Booking).where(Booking.property_id == prop_id))
        ).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_mysql_concurrent_slot_bookings_only_one_succeeds(mysql_engine):
    """Two simultaneous create_booking calls for the same slot — exactly one wins."""
    import asyncio

    Session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        owner = await _create_user(db, role="owner", email="conc-owner@example.com")
        buyer_a = await _create_user(db, role="buyer", email="conc-buyer-a@example.com")
        buyer_b = await _create_user(db, role="buyer", email="conc-buyer-b@example.com")
        prop = Property(
            id=new_id("prop"),
            owner_id=owner.id,
            title="Concurrent Slot Home",
            description="Property used to verify concurrent MySQL booking slot locking.",
            address="4 Race Lane",
            latitude=1.0,
            longitude=2.0,
            price=400_000,
            property_type="house",
            area_sqft=1800,
            bedrooms=4,
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
        buyer_a_out = UserOut.model_validate(buyer_a)
        buyer_b_out = UserOut.model_validate(buyer_b)

    payload = BookingCreate(
        property_id=prop_id,
        booking_date="2030-08-20T10:00:00+00:00",
        time_slot="11:00 AM",
    )

    async def attempt(user_out: UserOut):
        async with Session() as db:
            try:
                result = await create_booking(db, user_out, payload)
                await db.commit()
                return ("ok", result)
            except Exception as exc:
                await db.rollback()
                return ("err", type(exc).__name__, str(exc))

    outcomes = await asyncio.gather(attempt(buyer_a_out), attempt(buyer_b_out))
    successes = [o for o in outcomes if o[0] == "ok"]
    failures = [o for o in outcomes if o[0] == "err"]
    assert len(successes) == 1, outcomes
    assert len(failures) == 1, outcomes
    assert failures[0][1] in ("ConflictError", "IntegrityError"), failures

    async with Session() as db:
        rows = (
            await db.execute(select(Booking).where(Booking.property_id == prop_id))
        ).scalars().all()
        holding = [b for b in rows if b.slot_key]
        assert len(holding) == 1
