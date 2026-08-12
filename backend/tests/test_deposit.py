"""Deposit calculation tests."""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.deposit import calculate_deposit


def test_calculate_deposit_default_percent():
    settings = Settings(
        jwt_secret="test-secret-key-not-for-production-use-32",
        default_deposit_percent=0.10,
        environment="test",
    )
    assert calculate_deposit(500_000, settings) == 50_000.0


def test_calculate_deposit_rejects_invalid_price():
    settings = Settings(
        jwt_secret="test-secret-key-not-for-production-use-32",
        environment="test",
    )
    with pytest.raises(AppError):
        calculate_deposit(0, settings)
