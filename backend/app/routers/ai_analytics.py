"""Price estimate, recommendations, and analytics routes."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.ai import PriceEstimateInput
from app.schemas.user import UserOut
from app.services import ai as ai_service
from app.services import analytics as analytics_service

router = APIRouter(tags=["ai-analytics"])


@router.post("/ai/estimate-price")
async def estimate_price(
    body: PriceEstimateInput,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Similarity/heuristic price estimator (not a trained ML model)."""
    return await ai_service.estimate_price(db, body)


@router.get("/ai/recommendations")
async def recommendations(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    property_id: Optional[str] = None,
    limit: int = Query(6, ge=1, le=20),
):
    return await ai_service.get_recommendations(db, user, property_id, limit)


@router.get("/analytics/market-trends")
async def market_trends(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await analytics_service.market_trends(db)


@router.get("/analytics/buyer-behavior")
async def buyer_behavior(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await analytics_service.buyer_behavior(db)


@router.get("/analytics/dashboard")
async def dashboard(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await analytics_service.dashboard(db, user)
