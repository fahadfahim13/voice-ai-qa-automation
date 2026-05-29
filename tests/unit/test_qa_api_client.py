"""Unit tests for QaApiClient using respx mocked transport."""

from __future__ import annotations

import httpx
import pytest
import respx

from backend.qa_api import QaApiClient, QaApiError

BASE = "https://bizfinder.ai"


@pytest.fixture
def client():
    return QaApiClient(base_url=BASE, secret="test-secret", rps=100.0)


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_health_ok(respx_mock, client):
    respx_mock.get("/api/qa/health").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "service": "qa-read-api",
                "serverTime": "2026-05-14T00:12:34.381Z",
            },
        )
    )
    async with client as c:
        h = await c.health()
    assert h.ok is True
    assert h.service == "qa-read-api"


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_health_wrong_secret_raises(respx_mock, client):
    respx_mock.get("/api/qa/health").mock(
        return_value=httpx.Response(401, json={"error": "Unauthorized"})
    )
    async with client as c:
        with pytest.raises(QaApiError) as exc:
            await c.health()
    assert exc.value.status == 401


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_list_conversations(respx_mock, client):
    respx_mock.get("/api/qa/conversations").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "count": 1,
                "nextCursor": "cursor-1",
                "conversations": [
                    {
                        "id": "cmp3pknl1001k11wxbbuwbecw",
                        "sessionId": "voice-1778655521124-24klmm",
                        "siteId": "mk24x7.com",
                        "businessName": "Mukul",
                        "isVoice": True,
                        "satisfaction": None,
                        "score": None,
                        "metrics": None,
                        "createdAt": "2026-05-13T06:58:41.125Z",
                        "updatedAt": "2026-05-13T06:58:41.125Z",
                    }
                ],
            },
        )
    )
    async with client as c:
        page = await c.list_conversations(site_id="qa-judge", limit=5)
    assert page.count == 1
    assert page.conversations[0].sessionId == "voice-1778655521124-24klmm"
    assert page.nextCursor == "cursor-1"


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_get_conversation(respx_mock, client):
    sid = "voice-1778655521124-24klmm"
    respx_mock.get(f"/api/qa/conversations/{sid}").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "conversation": {
                    "id": "cmp3pknl1001k11wxbbuwbecw",
                    "sessionId": sid,
                    "siteId": "mk24x7.com",
                    "businessName": "Mukul",
                    "isVoice": True,
                    "satisfaction": None,
                    "score": None,
                    "metrics": None,
                    "createdAt": "2026-05-13T06:58:41.125Z",
                    "updatedAt": "2026-05-13T06:58:41.125Z",
                    "messages": [
                        {
                            "id": "m1",
                            "role": "assistant",
                            "content": "Hello",
                            "rating": None,
                            "createdAt": "2026-05-13T06:58:41.918Z",
                        },
                        {
                            "id": "m2",
                            "role": "user",
                            "content": "Hi",
                            "rating": None,
                            "createdAt": "2026-05-13T06:58:41.920Z",
                        },
                    ],
                },
            },
        )
    )
    async with client as c:
        conv = await c.get_conversation(sid)
    assert conv.sessionId == sid
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "assistant"


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_get_conversation_404(respx_mock, client):
    respx_mock.get("/api/qa/conversations/nope").mock(
        return_value=httpx.Response(404, json={"error": "Not found"})
    )
    async with client as c:
        with pytest.raises(QaApiError) as exc:
            await c.get_conversation("nope")
    assert exc.value.status == 404


@pytest.mark.asyncio
@respx.mock(base_url=BASE)
async def test_auth_gate_check(respx_mock, client):
    respx_mock.get(
        "/api/qa/health",
        headers={"X-QA-Secret": "deliberately-wrong"},
    ).mock(return_value=httpx.Response(401, json={"error": "Unauthorized"}))
    async with client as c:
        assert await c.auth_gate_check() is True
