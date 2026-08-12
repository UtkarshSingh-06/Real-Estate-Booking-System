"""Similarity-based price estimation and recommendations (not ML models)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PropertyStatus
from app.core.exceptions import NotFoundError
from app.models.booking import Booking
from app.models.property import Property
from app.schemas.ai import PriceEstimateInput
from app.schemas.user import UserOut
from app.services.property import serialize_property


def _heuristic_price(property_type: str, area_sqft: float, bedrooms: int, bathrooms: int) -> float:
    base_per_sqft = {"apartment": 180, "house": 220, "villa": 350, "condo": 200, "townhouse": 210}
    per_sqft = base_per_sqft.get(property_type.lower(), 200)
    room_factor = 1.0 + (bedrooms - 2) * 0.05 + (bathrooms - 2) * 0.03
    return max(50_000.0, area_sqft * per_sqft * max(0.7, min(1.3, room_factor)))


async def estimate_price(db: AsyncSession, data: PriceEstimateInput) -> dict:
    """Content/similarity heuristic estimator — not a trained ML model."""
    stmt = (
        select(Property)
        .where(
            and_(
                Property.status == PropertyStatus.PUBLISHED.value,
                Property.deleted_at.is_(None),
                Property.property_type == data.property_type,
            )
        )
        .limit(200)
    )
    result = await db.execute(stmt)
    similar = list(result.scalars().all())

    method = "heuristic_fallback"
    confidence = "low"
    if similar:
        prices = []
        for p in similar:
            area_diff = abs(p.area_sqft - data.area_sqft) / max(data.area_sqft, 1)
            bed_diff = abs(p.bedrooms - data.bedrooms)
            bath_diff = abs(p.bathrooms - data.bathrooms)
            weight = 1.0 / (1.0 + area_diff * 0.5 + bed_diff * 0.2 + bath_diff * 0.2)
            prices.append((p.price, weight))
        total_w = sum(w for _, w in prices)
        if total_w > 0:
            estimated = sum(p * w for p, w in prices) / total_w
            method = "similarity_weighted_average"
            confidence = "medium" if len(similar) >= 5 else "low"
        else:
            estimated = _heuristic_price(
                data.property_type, data.area_sqft, data.bedrooms, data.bathrooms
            )
    else:
        estimated = _heuristic_price(
            data.property_type, data.area_sqft, data.bedrooms, data.bathrooms
        )

    return {
        "estimated_price": round(estimated, 2),
        "currency": "USD",
        "based_on_listings": len(similar),
        "method": method,
        "confidence": confidence,
        "inputs": data.model_dump(),
    }


async def get_recommendations(
    db: AsyncSession,
    user: UserOut,
    property_id: Optional[str] = None,
    limit: int = 6,
) -> dict:
    limit = max(1, min(limit, 20))

    if property_id:
        result = await db.execute(
            select(Property).where(
                and_(
                    Property.id == property_id,
                    Property.status == PropertyStatus.PUBLISHED.value,
                    Property.deleted_at.is_(None),
                )
            )
        )
        prop = result.scalar_one_or_none()
        if not prop:
            raise NotFoundError("Property not found")

        stmt = (
            select(Property)
            .where(
                and_(
                    Property.status == PropertyStatus.PUBLISHED.value,
                    Property.deleted_at.is_(None),
                    Property.id != property_id,
                    Property.property_type == prop.property_type,
                    Property.price >= prop.price * 0.7,
                    Property.price <= prop.price * 1.3,
                    Property.area_sqft >= prop.area_sqft * 0.7,
                    Property.area_sqft <= prop.area_sqft * 1.3,
                )
            )
            .limit(limit)
        )
        similar = list((await db.execute(stmt)).scalars().all())
        if len(similar) < limit:
            similar_ids = [p.id for p in similar] + [property_id]
            extra = list(
                (
                    await db.execute(
                        select(Property)
                        .where(
                            and_(
                                Property.status == PropertyStatus.PUBLISHED.value,
                                Property.deleted_at.is_(None),
                                ~Property.id.in_(similar_ids),
                                Property.property_type == prop.property_type,
                            )
                        )
                        .limit(limit - len(similar))
                    )
                ).scalars().all()
            )
            similar = (similar + extra)[:limit]

        return {
            "recommendations": [serialize_property(p) for p in similar],
            "type": "similar",
            "strategy": "Same type within ~30% price and area band; backfill by type",
        }

    booked_ids = list(
        (
            await db.execute(
                select(Booking.property_id).where(Booking.user_id == user.id).limit(50)
            )
        ).scalars().all()
    )

    if not booked_ids:
        top = (
            await db.execute(
                select(Booking.property_id, func.count(Booking.id).label("count"))
                .group_by(Booking.property_id)
                .order_by(desc("count"))
                .limit(limit * 2)
            )
        ).all()
        top_ids = [row[0] for row in top]
        if not top_ids:
            props = list(
                (
                    await db.execute(
                        select(Property)
                        .where(
                            Property.status == PropertyStatus.PUBLISHED.value,
                            Property.deleted_at.is_(None),
                        )
                        .limit(limit)
                    )
                ).scalars().all()
            )
            strategy = "Fallback: newest published listings"
        else:
            props = list(
                (
                    await db.execute(
                        select(Property).where(
                            and_(
                                Property.id.in_(top_ids),
                                Property.status == PropertyStatus.PUBLISHED.value,
                                Property.deleted_at.is_(None),
                            )
                        ).limit(limit)
                    )
                ).scalars().all()
            )
            strategy = "Trending: most booked published listings"
        return {
            "recommendations": [serialize_property(p) for p in props[:limit]],
            "type": "trending",
            "strategy": strategy,
        }

    booked_props = list(
        (
            await db.execute(
                select(Property).where(
                    and_(
                        Property.id.in_(list(set(booked_ids))),
                        Property.status == PropertyStatus.PUBLISHED.value,
                        Property.deleted_at.is_(None),
                    )
                ).limit(20)
            )
        ).scalars().all()
    )
    if not booked_props:
        props = list(
            (
                await db.execute(
                    select(Property)
                    .where(
                        Property.status == PropertyStatus.PUBLISHED.value,
                        Property.deleted_at.is_(None),
                    )
                    .limit(limit)
                )
            ).scalars().all()
        )
        return {
            "recommendations": [serialize_property(p) for p in props],
            "type": "trending",
            "strategy": "Fallback: published listings",
        }

    types = list({p.property_type for p in booked_props})
    avg_price = sum(p.price for p in booked_props) / len(booked_props)
    recs = list(
        (
            await db.execute(
                select(Property)
                .where(
                    and_(
                        Property.status == PropertyStatus.PUBLISHED.value,
                        Property.deleted_at.is_(None),
                        ~Property.id.in_(list(set(booked_ids))),
                        Property.property_type.in_(types),
                        Property.price >= avg_price * 0.6,
                        Property.price <= avg_price * 1.4,
                    )
                )
                .limit(limit)
            )
        ).scalars().all()
    )
    return {
        "recommendations": [serialize_property(p) for p in recs],
        "type": "personalized",
        "strategy": "Based on types and price band from your past bookings",
    }
