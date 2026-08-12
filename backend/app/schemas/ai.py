"""AI / analytics schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PriceEstimateInput(BaseModel):
    property_type: str = Field(..., min_length=2, max_length=50)
    area_sqft: float = Field(..., gt=0)
    bedrooms: int = Field(..., ge=0, le=50)
    bathrooms: int = Field(..., ge=0, le=50)
    amenities: List[str] = Field(default_factory=list, max_length=50)


class PriceEstimateOut(BaseModel):
    estimated_price: float
    currency: str = "USD"
    based_on_listings: int
    method: str
    confidence: str
    inputs: Dict[str, Any]


class RecommendationOut(BaseModel):
    recommendations: List[Dict[str, Any]]
    type: str
    strategy: str
