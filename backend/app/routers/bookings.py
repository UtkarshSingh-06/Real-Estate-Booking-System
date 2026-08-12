"""Booking routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.booking import BookingCreate, BookingStatusUpdate
from app.schemas.user import UserOut
from app.services import booking as booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("")
async def create_booking(
    body: BookingCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await booking_service.create_booking(db, user, body)


@router.get("")
async def list_bookings(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await booking_service.list_user_bookings(db, user, page, page_size)
    return {
        "bookings": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.get("/owner")
async def owner_bookings(
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await booking_service.list_owner_bookings(db, user, page, page_size)
    return {
        "bookings": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


@router.put("/{booking_id}/status")
async def update_status(
    booking_id: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = Query(..., min_length=3, max_length=30),
):
    """Update booking status. Query param kept for frontend compatibility."""
    return await booking_service.transition_booking(db, user, booking_id, status)


@router.post("/{booking_id}/transition")
async def transition(
    booking_id: str,
    body: BookingStatusUpdate,
    user: Annotated[UserOut, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await booking_service.transition_booking(
        db, user, booking_id, body.status.value
    )
