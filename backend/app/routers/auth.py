"""Auth routes."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import AppError
from app.db.session import get_db
from app.schemas.user import AuthResponse, GoogleAuthRequest, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    body: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await auth_service.authenticate_with_google(db, body.id_token)


@router.post("/session", response_model=AuthResponse, deprecated=True)
async def legacy_session(
    body: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Legacy alias — use POST /auth/google with a GIS id_token."""
    return await auth_service.authenticate_with_google(db, body.id_token)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[UserOut, Depends(get_current_user)]):
    return user


@router.post("/logout")
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("Not authenticated", status_code=status.HTTP_401_UNAUTHORIZED)
    await auth_service.logout(db, authorization[7:].strip())
    return {"message": "Logged out successfully"}
