"""Async client for the BizFinder QA Read API.

Endpoints (read-only, isVoice=true scope):
  GET /api/qa/health
  GET /api/qa/conversations?siteId&since&limit&cursor
  GET /api/qa/conversations/<id-or-sessionId>

Auth: X-QA-Secret header.
Rate limit: self-imposed via aiolimiter (handover asks <= 1 req/sec).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.qa_api.models import (
    QaConversation,
    QaConversationEnvelope,
    QaConversationList,
    QaConversationSummary,
    QaHealth,
)
from backend.settings import get_settings


class QaApiError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"QA API {status}: {body[:200]}")
        self.status = status
        self.body = body


class QaApiClient:
    """Use as async context manager. Single-secret X-QA-Secret auth."""

    def __init__(
        self,
        base_url: str | None = None,
        secret: str | None = None,
        rps: float | None = None,
        timeout: float = 15.0,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.qa_base_url).rstrip("/")
        self.secret = secret or s.qa_shared_secret
        self._timeout = timeout
        self._limiter = AsyncLimiter(max_rate=rps or s.qa_rate_limit_rps, time_period=1.0)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> QaApiClient:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={
                "X-QA-Secret": self.secret,
                "Accept": "application/json",
                "User-Agent": "bizfinder-voice-qa/0.1",
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, **params) -> httpx.Response:
        assert self._client is not None, "Use as async context manager"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
            retry=retry_if_exception_type((httpx.TransportError, httpx.ReadTimeout)),
            reraise=True,
        ):
            with attempt:
                async with self._limiter:
                    logger.debug("GET {} params={}", path, params)
                    resp = await self._client.get(path, params=params or None)
        return resp

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise QaApiError(resp.status_code, resp.text)

    async def health(self) -> QaHealth:
        resp = await self._get("/api/qa/health")
        self._check(resp)
        return QaHealth.model_validate(resp.json())

    async def list_conversations(
        self,
        *,
        site_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> QaConversationList:
        params: dict[str, str | int] = {"limit": limit}
        if site_id:
            params["siteId"] = site_id
        if since:
            params["since"] = since.isoformat()
        if cursor:
            params["cursor"] = cursor
        resp = await self._get("/api/qa/conversations", **params)
        self._check(resp)
        return QaConversationList.model_validate(resp.json())

    async def iter_conversations(
        self,
        *,
        site_id: str | None = None,
        since: datetime | None = None,
        page_size: int = 50,
    ) -> AsyncIterator[QaConversationSummary]:
        cursor: str | None = None
        while True:
            page = await self.list_conversations(
                site_id=site_id, since=since, limit=page_size, cursor=cursor
            )
            for row in page.conversations:
                yield row
            if not page.nextCursor or not page.conversations:
                return
            cursor = page.nextCursor

    async def get_conversation(self, id_or_session_id: str) -> QaConversation:
        resp = await self._get(f"/api/qa/conversations/{id_or_session_id}")
        self._check(resp)
        return QaConversationEnvelope.model_validate(resp.json()).conversation

    async def auth_gate_check(self) -> bool:
        """Probe with the wrong secret; expect 401. Returns True if gate is enforced."""
        assert self._client is not None
        async with self._limiter:
            resp = await self._client.get(
                "/api/qa/health", headers={"X-QA-Secret": "deliberately-wrong"}
            )
        return resp.status_code == 401


@asynccontextmanager
async def qa_client(**kw) -> AsyncIterator[QaApiClient]:
    async with QaApiClient(**kw) as c:
        yield c
