"""Property schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import PropertyStatus, PropertyType
from app.schemas.common import ORMModel


class PropertyCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10, max_length=10000)
    address: str = Field(..., min_length=5, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    price: float = Field(..., gt=0)
    property_type: PropertyType | str
    area_sqft: float = Field(..., gt=0)
    bedrooms: int = Field(..., ge=0, le=50)
    bathrooms: int = Field(..., ge=0, le=50)
    amenities: List[str] = Field(default_factory=list, max_length=50)
    images: List[str] = Field(default_factory=list, max_length=30)
    status: PropertyStatus = PropertyStatus.PUBLISHED

    @field_validator("amenities", "images")
    @classmethod
    def validate_string_lists(cls, values: List[str]) -> List[str]:
        cleaned = []
        for item in values:
            if not isinstance(item, str):
                raise ValueError("List items must be strings")
            item = item.strip()
            if item:
                cleaned.append(item[:500])
        return cleaned


class PropertyUpdate(PropertyCreate):
    pass


class PropertyOut(ORMModel):
    id: str
    owner_id: str
    title: str
    description: str
    address: str
    latitude: float
    longitude: float
    price: float
    property_type: str
    area_sqft: float
    bedrooms: int
    bathrooms: int
    amenities: List[str] = []
    images: List[str] = []
    status: str
    created_at: datetime


class PropertySearchQuery(BaseModel):
    query: Optional[str] = Field(None, max_length=200)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    property_type: Optional[str] = None
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    min_area_sqft: Optional[float] = Field(None, ge=0)
    max_area_sqft: Optional[float] = Field(None, ge=0)
    amenities: Optional[List[str]] = None
    status: Optional[str] = PropertyStatus.PUBLISHED.value
    sort_by: Optional[str] = Field("created_at", pattern="^(created_at|price|area_sqft|bedrooms)$")
    sort_dir: Optional[str] = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
