"""Authentication service."""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import AppError
from app.core.security import create_access_token, verify_google_id_token
from app.core.utils import new_id, utcnow
from app.models.user import User, UserSession
from app.schemas.user import AuthResponse, UserOut

logger = logging.getLogger(__name__)


async def authenticate_with_google(db: AsyncSession, id_token: str) -> AuthResponse:
    try:
        claims = verify_google_id_token(id_token)
    except Exception as exc:
        logger.warning("Google token verification failed: %s", exc)
        raise AppError("Invalid Google token", status_code=400, code="invalid_google_token") from exc

    email = claims["email"]
    name = claims.get("name") or email.split("@")[0]
    picture = claims.get("picture")
    google_id = claims.get("sub") or email

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Deterministic ID from Google subject for stable identity across reinstalls
        user_id = f"user_{hashlib.sha256(google_id.encode()).hexdigest()[:16]}"
        user = User(
            id=user_id,
            email=email,
            name=name,
            picture=picture,
            role=UserRole.BUYER.value,
            created_at=utcnow(),
        )
        db.add(user)
        await db.flush()
    else:
        user.name = name
        user.picture = picture

    token, expires_at = create_access_token(user.id, user.email)
    db.add(
        UserSession(
            user_id=user.id,
            session_token=token,
            expires_at=expires_at,
            created_at=utcnow(),
        )
    )
    await db.flush()

    return AuthResponse(session_token=token, user=UserOut.model_validate(user))


async def logout(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(UserSession).where(UserSession.session_token == token))
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.flush()
