"""Analytics service — permission-aware market and owner metrics."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BookingStatus, PropertyStatus, UserRole
from app.models.booking import Booking
from app.models.property import Property
from app.schemas.user import UserOut
from app.services.property import serialize_property


async def market_trends(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Property).where(
            Property.status == PropertyStatus.PUBLISHED.value,
            Property.deleted_at.is_(None),
        )
    )
    all_props = list(result.scalars().all())
    by_period: Dict[str, List[float]] = defaultdict(list)
    for p in all_props:
        created = p.created_at or datetime.now(timezone.utc)
        period = created.strftime("%Y-%m")
        by_period[period].append(p.price)

    results = []
    for period in sorted(by_period.keys()):
        prices = by_period[period]
        results.append(
            {
                "period": period,
                "year": int(period[:4]),
                "month": int(period[5:7]),
                "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
                "count": len(prices),
            }
        )
    return {"market_trends": results}


async def buyer_behavior(db: AsyncSession) -> dict:
    by_type_rows = (
        await db.execute(
            select(Property.property_type, func.count(Booking.id).label("bookings"))
            .join(Booking, Booking.property_id == Property.id)
            .group_by(Property.property_type)
            .order_by(desc("bookings"))
            .limit(20)
        )
    ).all()
    by_type = [{"property_type": row[0], "bookings": row[1]} for row in by_type_rows]

    top_bookings = (
        await db.execute(
            select(Booking.property_id, func.count(Booking.id).label("bookings"))
            .group_by(Booking.property_id)
            .order_by(desc("bookings"))
            .limit(10)
        )
    ).all()
    id_to_count = {row[0]: row[1] for row in top_bookings}
    top_ids = list(id_to_count.keys())
    props_list: list[dict] = []
    if top_ids:
        props = list(
            (
                await db.execute(
                    select(Property).where(
                        and_(
                            Property.id.in_(top_ids),
                            Property.status == PropertyStatus.PUBLISHED.value,
                            Property.deleted_at.is_(None),
                        )
                    )
                )
            ).scalars().all()
        )
        props_list = [
            {**serialize_property(p), "booking_count": id_to_count.get(p.id, 0)}
            for p in props
        ]
        props_list.sort(key=lambda x: x["booking_count"], reverse=True)

    return {
        "bookings_by_property_type": by_type,
        "most_popular_properties": props_list,
    }


async def dashboard(db: AsyncSession, user: UserOut) -> dict:
    total_properties = await db.scalar(
        select(func.count(Property.id)).where(
            Property.status == PropertyStatus.PUBLISHED.value,
            Property.deleted_at.is_(None),
        )
    )
    total_bookings = await db.scalar(select(func.count(Booking.id)))
    confirmed = await db.scalar(
        select(func.count(Booking.id)).where(Booking.status == BookingStatus.CONFIRMED.value)
    )
    avg_price = await db.scalar(
        select(func.avg(Property.price)).where(
            Property.status == PropertyStatus.PUBLISHED.value,
            Property.deleted_at.is_(None),
        )
    )
    conversion = 0.0
    if total_bookings:
        conversion = round((confirmed or 0) / total_bookings * 100, 2)

    payload: dict[str, Any] = {
        "total_listings": total_properties or 0,
        "total_bookings": total_bookings or 0,
        "confirmed_bookings": confirmed or 0,
        "conversion_rate_percent": conversion,
        "average_listing_price": round(float(avg_price or 0), 2),
        "currency": "USD",
    }

    if user.role in (UserRole.OWNER.value, UserRole.AGENT.value, UserRole.ADMIN.value):
        my_listings = await db.scalar(
            select(func.count(Property.id)).where(
                Property.owner_id == user.id,
                Property.deleted_at.is_(None),
            )
        )
        my_bookings = await db.scalar(
            select(func.count(Booking.id)).where(Booking.owner_id == user.id)
        )
        my_confirmed = await db.scalar(
            select(func.count(Booking.id)).where(
                and_(
                    Booking.owner_id == user.id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                )
            )
        )
        payload["owner_metrics"] = {
            "my_listings": my_listings or 0,
            "my_bookings": my_bookings or 0,
            "my_confirmed_bookings": my_confirmed or 0,
            "my_conversion_rate_percent": round(
                ((my_confirmed or 0) / my_bookings * 100) if my_bookings else 0, 2
            ),
        }

    return payload
