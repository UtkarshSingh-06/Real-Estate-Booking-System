"""Property routes."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.property import PropertyCreate, PropertySearchQuery
from app.schemas.user import UserOut
from app.services import property as property_service

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("")
async def list_properties(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
):
    query = PropertySearchQuery(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir)
    items, total = await property_service.list_properties(db, query)
    return {
        "properties": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.get("/my")
async def my_properties(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await property_service.get_my_properties(db, user, page, page_size)
    return {
        "properties": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.get("/search/realtime")
async def realtime_search(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    property_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
):
    query = PropertySearchQuery(
        query=q,
        min_price=min_price,
        max_price=max_price,
        property_type=property_type,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        page=1,
        page_size=limit,
    )
    items, total = await property_service.list_properties(db, query)
    return {"properties": items, "total": total}


@router.post("/search")
async def search_properties(
    body: PropertySearchQuery,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    items, total = await property_service.list_properties(db, body)
    return {
        "properties": items,
        "total": total,
        "page": body.page,
        "page_size": body.page_size,
        "has_next": (body.page * body.page_size) < total,
    }


@router.get("/{property_id}")
async def get_property(
    property_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await property_service.get_property(db, property_id, user)


@router.post("")
async def create_property(
    body: PropertyCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await property_service.create_property(db, user, body)


@router.put("/{property_id}")
async def update_property(
    property_id: str,
    body: PropertyCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await property_service.update_property(db, user, property_id, body)


@router.delete("/{property_id}")
async def delete_property(
    property_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await property_service.archive_property(db, user, property_id)
