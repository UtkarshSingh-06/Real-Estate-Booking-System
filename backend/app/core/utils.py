"""ID and time utilities."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Collision-resistant prefixed UUID identifier."""
    return f"{prefix}_{uuid4().hex}"


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_date(value: datetime | date | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return ensure_utc(value).date()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def make_slot_key(property_id: str, booking_date: date | datetime | str, time_slot: str) -> str:
    d = to_date(booking_date)
    return f"{property_id}|{d.isoformat()}|{time_slot.strip()}"
