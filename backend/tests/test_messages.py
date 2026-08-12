"""Messaging authorization tests."""
from __future__ import annotations

import pytest

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_send_and_list_messages(client, buyer, owner, published_property):
    send = await client.post(
        "/api/messages",
        headers=auth_header(buyer),
        json={
            "receiver_id": owner.id,
            "property_id": published_property.id,
            "message": "Is this still available?",
        },
    )
    assert send.status_code == 200
    conversation_id = send.json()["conversation_id"]

    msgs = await client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth_header(buyer),
    )
    assert msgs.status_code == 200
    assert len(msgs.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_cannot_read_others_conversation(
    client, buyer, owner, other_buyer, published_property
):
    send = await client.post(
        "/api/messages",
        headers=auth_header(buyer),
        json={
            "receiver_id": owner.id,
            "property_id": published_property.id,
            "message": "Private note",
        },
    )
    conversation_id = send.json()["conversation_id"]

    stolen = await client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth_header(other_buyer),
    )
    assert stolen.status_code == 403


@pytest.mark.asyncio
async def test_attachments_rejected(client, buyer, owner):
    res = await client.post(
        "/api/messages",
        headers=auth_header(buyer),
        json={
            "receiver_id": owner.id,
            "message": "See attachment",
            "attachment_url": "https://evil.example/file.exe",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_conversations_only_own(client, buyer, owner, other_buyer, published_property):
    await client.post(
        "/api/messages",
        headers=auth_header(buyer),
        json={
            "receiver_id": owner.id,
            "property_id": published_property.id,
            "message": "Hello owner",
        },
    )
    mine = await client.get("/api/conversations", headers=auth_header(buyer))
    theirs = await client.get("/api/conversations", headers=auth_header(other_buyer))
    assert mine.status_code == 200
    assert theirs.status_code == 200
    assert theirs.json()["total"] == 0
    assert mine.json()["total"] >= 1
