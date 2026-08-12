"""Shared enums for domain statuses and roles."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    BUYER = "buyer"
    OWNER = "owner"
    AGENT = "agent"
    ADMIN = "admin"


class PropertyStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNAVAILABLE = "unavailable"
    ARCHIVED = "archived"


class PropertyType(str, Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    LAND = "land"
    OTHER = "other"


class BookingStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    PAYMENT_PENDING = "payment_pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"

    # Legacy aliases accepted on read for older rows
    PENDING = "pending"  # maps conceptually to REQUESTED


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentTransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"


# Statuses that hold a viewing slot
SLOT_HOLDING_STATUSES = {
    BookingStatus.REQUESTED.value,
    BookingStatus.APPROVED.value,
    BookingStatus.PAYMENT_PENDING.value,
    BookingStatus.CONFIRMED.value,
    # legacy
    "pending",
}


ALLOWED_BOOKING_TRANSITIONS: dict[str, set[str]] = {
    BookingStatus.REQUESTED.value: {
        BookingStatus.APPROVED.value,
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    },
    "pending": {  # legacy
        BookingStatus.APPROVED.value,
        BookingStatus.REJECTED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    },
    BookingStatus.APPROVED.value: {
        BookingStatus.PAYMENT_PENDING.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
        BookingStatus.REJECTED.value,
    },
    BookingStatus.PAYMENT_PENDING.value: {
        BookingStatus.CONFIRMED.value,
        BookingStatus.CANCELLED.value,
        BookingStatus.EXPIRED.value,
    },
    BookingStatus.CONFIRMED.value: {
        BookingStatus.CANCELLED.value,
    },
    BookingStatus.REJECTED.value: set(),
    BookingStatus.CANCELLED.value: set(),
    BookingStatus.EXPIRED.value: set(),
}
