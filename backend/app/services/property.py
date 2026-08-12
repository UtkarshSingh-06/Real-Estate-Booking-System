"""Property management service."""
from __future__ import annotations

import logging
from typing import Optional, Sequence, Tuple

from sqlalchemy import Select, and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import PropertyStatus, UserRole
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.utils import new_id, utcnow
from app.models.booking import Booking
from app.models.property import Property
from app.schemas.property import PropertyCreate, PropertySearchQuery
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)


def _geocode(address: str) -> tuple[float, float]:
    settings = get_settings()
    if settings.google_maps_api_key:
        try:
            import googlemaps

            client = googlemaps.Client(key=settings.google_maps_api_key)
            result = client.geocode(address)
            if result:
                loc = result[0]["geometry"]["location"]
                return float(loc["lat"]), float(loc["lng"])
        except Exception as exc:
            logger.warning("Geocoding failed: %s", exc)
    return 40.7128, -74.0060


def serialize_property(prop: Property) -> dict:
    return {
        "id": prop.id,
        "owner_id": prop.owner_id,
        "title": prop.title,
        "description": prop.description,
        "address": prop.address,
        "latitude": prop.latitude,
        "longitude": prop.longitude,
        "price": prop.price,
        "property_type": prop.property_type,
        "area_sqft": prop.area_sqft,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "amenities": prop.amenities or [],
        "images": prop.images or [],
        "status": prop.status,
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
    }


def _apply_search_filters(stmt: Select, query: PropertySearchQuery) -> Select:
    conditions = [Property.deleted_at.is_(None)]
    status = query.status or PropertyStatus.PUBLISHED.value
    conditions.append(Property.status == status)

    if query.min_price is not None:
        conditions.append(Property.price >= query.min_price)
    if query.max_price is not None:
        conditions.append(Property.price <= query.max_price)
    if query.property_type:
        conditions.append(Property.property_type == query.property_type)
    if query.bedrooms is not None:
        conditions.append(Property.bedrooms >= query.bedrooms)
    if query.bathrooms is not None:
        conditions.append(Property.bathrooms >= query.bathrooms)
    if query.min_area_sqft is not None:
        conditions.append(Property.area_sqft >= query.min_area_sqft)
    if query.max_area_sqft is not None:
        conditions.append(Property.area_sqft <= query.max_area_sqft)
    if query.query and query.query.strip():
        term = f"%{query.query.strip()}%"
        conditions.append(
            or_(
                Property.title.ilike(term),
                Property.description.ilike(term),
                Property.address.ilike(term),
            )
        )
    if query.amenities:
        # JSON contains check is DB-specific; filter in Python after fetch for amenity subsets
        pass

    return stmt.where(and_(*conditions))


async def list_properties(
    db: AsyncSession,
    query: PropertySearchQuery,
) -> Tuple[list[dict], int]:
    base = _apply_search_filters(select(Property), query)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = int(await db.scalar(count_stmt) or 0)

    sort_col = {
        "created_at": Property.created_at,
        "price": Property.price,
        "area_sqft": Property.area_sqft,
        "bedrooms": Property.bedrooms,
    }.get(query.sort_by or "created_at", Property.created_at)
    order = desc(sort_col) if (query.sort_dir or "desc") == "desc" else asc(sort_col)

    offset = (query.page - 1) * query.page_size
    result = await db.execute(base.order_by(order).offset(offset).limit(query.page_size))
    props = list(result.scalars().all())

    if query.amenities:
        wanted = {a.lower() for a in query.amenities}
        props = [
            p
            for p in props
            if wanted.issubset({str(a).lower() for a in (p.amenities or [])})
        ]

    return [serialize_property(p) for p in props], total


async def get_property(db: AsyncSession, property_id: str, user: Optional[UserOut] = None) -> dict:
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise NotFoundError("Property not found")

    is_owner = bool(user and (prop.owner_id == user.id or user.role == UserRole.ADMIN.value))
    if prop.deleted_at is not None or prop.status in (
        PropertyStatus.ARCHIVED.value,
        PropertyStatus.DRAFT.value,
        PropertyStatus.UNAVAILABLE.value,
    ):
        if not is_owner:
            raise NotFoundError("Property not found")

    return serialize_property(prop)


async def get_my_properties(
    db: AsyncSession, user: UserOut, page: int = 1, page_size: int = 20
) -> Tuple[list[dict], int]:
    base = select(Property).where(Property.owner_id == user.id, Property.deleted_at.is_(None))
    total = int(
        await db.scalar(
            select(func.count()).select_from(base.subquery())
        )
        or 0
    )
    result = await db.execute(
        base.order_by(desc(Property.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_property(p) for p in result.scalars().all()], total


async def create_property(db: AsyncSession, user: UserOut, data: PropertyCreate) -> dict:
    if user.role not in (UserRole.OWNER.value, UserRole.AGENT.value, UserRole.ADMIN.value):
        raise ForbiddenError("Only owners/agents can create properties")

    latitude = data.latitude
    longitude = data.longitude
    if latitude is None or longitude is None:
        latitude, longitude = _geocode(data.address)

    prop = Property(
        id=new_id("prop"),
        owner_id=user.id,
        title=data.title,
        description=data.description,
        address=data.address,
        latitude=latitude,
        longitude=longitude,
        price=data.price,
        property_type=str(data.property_type.value if hasattr(data.property_type, "value") else data.property_type),
        area_sqft=data.area_sqft,
        bedrooms=data.bedrooms,
        bathrooms=data.bathrooms,
        amenities=data.amenities,
        images=data.images,
        status=data.status.value if hasattr(data.status, "value") else str(data.status),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(prop)
    await db.flush()
    return {"id": prop.id, "message": "Property created successfully"}


async def update_property(
    db: AsyncSession, user: UserOut, property_id: str, data: PropertyCreate
) -> dict:
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.deleted_at.is_(None))
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise NotFoundError("Property not found")
    if prop.owner_id != user.id and user.role != UserRole.ADMIN.value:
        raise ForbiddenError("Not authorized")

    prop.title = data.title
    prop.description = data.description
    prop.address = data.address
    if data.latitude is not None:
        prop.latitude = data.latitude
    if data.longitude is not None:
        prop.longitude = data.longitude
    prop.price = data.price
    prop.property_type = str(
        data.property_type.value if hasattr(data.property_type, "value") else data.property_type
    )
    prop.area_sqft = data.area_sqft
    prop.bedrooms = data.bedrooms
    prop.bathrooms = data.bathrooms
    prop.amenities = data.amenities
    prop.images = data.images
    prop.status = data.status.value if hasattr(data.status, "value") else str(data.status)
    prop.updated_at = utcnow()
    await db.flush()
    return {"message": "Property updated successfully"}


async def archive_property(db: AsyncSession, user: UserOut, property_id: str) -> dict:
    """Soft-delete / archive a property. Preserves historical bookings."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.deleted_at.is_(None))
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise NotFoundError("Property not found")
    if prop.owner_id != user.id and user.role != UserRole.ADMIN.value:
        raise ForbiddenError("Not authorized")

    booking_count = await db.scalar(
        select(func.count(Booking.id)).where(Booking.property_id == property_id)
    )
    prop.status = PropertyStatus.ARCHIVED.value
    prop.deleted_at = utcnow()
    prop.updated_at = utcnow()
    await db.flush()
    return {
        "message": "Property archived successfully",
        "preserved_bookings": int(booking_count or 0),
    }
