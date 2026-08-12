"""Authentication and authorization tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_authorized(client, buyer):
    res = await client.get("/api/auth/me", headers=auth_header(buyer))
    assert res.status_code == 200
    assert res.json()["email"] == "buyer@example.com"


@pytest.mark.asyncio
async def test_google_auth_success(client, db_session):
    claims = {
        "email": "newuser@example.com",
        "name": "New User",
        "picture": "https://example.com/p.png",
        "sub": "google-sub-123",
        "iss": "accounts.google.com",
    }
    with patch("app.services.auth.verify_google_id_token", return_value=claims):
        res = await client.post("/api/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert res.status_code == 200
    body = res.json()
    assert "session_token" in body
    assert body["user"]["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_google_auth_invalid_token(client):
    with patch(
        "app.services.auth.verify_google_id_token",
        side_effect=ValueError("bad token"),
    ):
        res = await client.post("/api/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_property_forbidden_for_buyer(client, buyer):
    res = await client.post(
        "/api/properties",
        headers=auth_header(buyer),
        json={
            "title": "Nice Home Place",
            "description": "A detailed description of the property here.",
            "address": "1 Test Lane",
            "price": 100000,
            "property_type": "house",
            "area_sqft": 1000,
            "bedrooms": 3,
            "bathrooms": 2,
            "latitude": 1.0,
            "longitude": 2.0,
        },
    )
    assert res.status_code == 403
