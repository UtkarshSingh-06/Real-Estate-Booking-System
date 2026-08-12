"""Server-side deposit calculation — clients must never set monetary amounts."""
from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError


def calculate_deposit(property_price: float, settings: Settings | None = None) -> float:
    """Calculate viewing deposit from property price and configured policy.

    Policy: ``round(property_price * default_deposit_percent, 2)`` with a minimum
    of ``0.01`` USD. Override ``DEFAULT_DEPOSIT_PERCENT`` in environment.
    """
    settings = settings or get_settings()
    if property_price <= 0:
        raise AppError("Property price must be positive to calculate deposit", status_code=400)

    percent = settings.default_deposit_percent
    if percent <= 0 or percent > 1:
        raise AppError("Invalid deposit policy configuration", status_code=500)

    amount = round(property_price * percent, 2)
    if amount <= 0:
        raise AppError("Calculated deposit must be positive", status_code=400)
    return amount
