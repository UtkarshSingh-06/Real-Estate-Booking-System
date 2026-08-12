"""Socket.IO authentication helpers."""
from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.websocket.server import _extract_token, _resolve_user_id


def test_extract_token_from_auth_dict():
    token = _extract_token({"token": "abc123"}, {})
    assert token == "abc123"


def test_extract_token_from_query_string():
    token = _extract_token(None, {"QUERY_STRING": "token=xyz"})
    assert token == "xyz"


@pytest.mark.asyncio
async def test_resolve_user_id_from_jwt(buyer):
    token, _ = create_access_token(buyer.id, buyer.email)
    user_id = await _resolve_user_id(token)
    assert user_id == buyer.id


@pytest.mark.asyncio
async def test_resolve_user_id_invalid():
    user_id = await _resolve_user_id("not-a-valid-token")
    assert user_id is None
