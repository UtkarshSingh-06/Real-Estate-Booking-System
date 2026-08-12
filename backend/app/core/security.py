"""Security helpers: JWT, passwordless session tokens, Google ID token verification."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import Settings, get_settings


def create_access_token(
    user_id: str,
    email: str,
    settings: Optional[Settings] = None,
) -> tuple[str, datetime]:
    settings = settings or get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(
    token: str,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    settings = settings or get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def verify_google_id_token(
    token: str,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Verify a Google Identity Services ID token and return claims."""
    settings = settings or get_settings()
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")

    request = google_requests.Request()
    claims = google_id_token.verify_oauth2_token(
        token,
        request,
        settings.google_client_id,
    )
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid Google token issuer")
    if not claims.get("email"):
        raise ValueError("Email missing from Google token")
    return claims
