"""Legacy database module — re-exports the modular ORM for older imports."""
from app.db.session import get_db, init_db, engine, AsyncSessionLocal
from app.db.base import Base
from app.models import (
    User,
    UserSession,
    Property,
    Booking,
    Conversation,
    Message,
    PaymentTransaction,
)

__all__ = [
    "get_db",
    "init_db",
    "engine",
    "AsyncSessionLocal",
    "Base",
    "User",
    "UserSession",
    "Property",
    "Booking",
    "Conversation",
    "Message",
    "PaymentTransaction",
]
