"""AI estimator, recommendations, analytics, pagination."""
from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_price_estimate_honest_metadata(client, buyer, published_property):
    res = await client.post(
        "/api/ai/estimate-price",
        headers=auth_header(buyer),
        json={
            "property_type": "apartment",
            "area_sqft": 1100,
            "bedrooms": 2,
            "bathrooms": 2,
            "amenities": [],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "estimated_price" in body
    assert body["method"] in ("similarity_weighted_average", "heuristic_fallback")
    assert body["confidence"] in ("low", "medium", "high")
    assert "based_on_listings" in body


@pytest.mark.asyncio
async def test_recommendations(client, buyer, published_property):
    res = await client.get(
        f"/api/ai/recommendations?property_id={published_property.id}&limit=3",
        headers=auth_header(buyer),
    )
    assert res.status_code == 200
    assert "strategy" in res.json()
    assert res.json()["type"] == "similar"


@pytest.mark.asyncio
async def test_analytics_dashboard(client, buyer, published_property):
    res = await client.get("/api/analytics/dashboard", headers=auth_header(buyer))
    assert res.status_code == 200
    body = res.json()
    assert body["total_listings"] >= 1
    assert "conversion_rate_percent" in body
    assert "average_listing_price" in body


@pytest.mark.asyncio
async def test_pagination_metadata(client, buyer, published_property):
    res = await client.get(
        "/api/properties?page=1&page_size=1",
        headers=auth_header(buyer),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert "has_next" in body
    assert "total" in body
