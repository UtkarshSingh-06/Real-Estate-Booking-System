"""Shared FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserSession
from app.schemas.user import UserOut


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Optional[str] = Header(None),
) -> UserOut:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id: Optional[str] = None
    try:
        payload = decode_access_token(token, settings)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        # Backward-compatible session token lookup
        result = await db.execute(
            select(UserSession).where(UserSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )
        user_id = session.user_id

    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return UserOut.model_validate(db_user)


async def get_optional_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Optional[str] = Header(None),
) -> Optional[UserOut]:
    if not authorization:
        return None
    try:
        return await get_current_user(db, settings, authorization)
    except HTTPException:
        return None


def require_roles(*roles: str):
    async def _checker(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this action",
            )
        return user

    return _checker
