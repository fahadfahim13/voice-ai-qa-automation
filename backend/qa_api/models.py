"""Pydantic mirrors of the QA Read API response shapes.

Matches the shapes documented in `Voice Judge-QA - Final Handover.pdf` §13.
Generous with Optional[] because the live shape under-populates some fields
(e.g. `metrics` is `null` on freshly-created Conversation rows).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QaTurnMetric(BaseModel):
    """One row in Conversation.metrics.turns[] (per-turn timing breakdown).

    Field names match the handover doc §11; live responses may add or omit fields.
    """

    model_config = ConfigDict(extra="allow")

    turn: int | None = None
    stt_ms: float | None = None
    llm_ttfb_ms: float | None = None
    llm_end_ms: float | None = None
    tts_ttfb_ms: float | None = None
    total_ms: float | None = None
    user_stopped_at: float | None = None
    llm_token_count: int | None = None


class QaMetrics(BaseModel):
    """Container shape actually returned by the live API.

    The handover doc §11 shows metrics as a bare list of turn rows. The live
    /api/qa/conversations response wraps it in {startedAt, voice, turns:[]}.
    We accept either form via field_validator on the parent model.
    """

    model_config = ConfigDict(extra="allow")

    startedAt: datetime | None = None
    voice: str | None = None
    turns: list[QaTurnMetric] = Field(default_factory=list)


class QaMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    rating: int | None = None
    createdAt: datetime


class QaConversationSummary(BaseModel):
    """Row in /api/qa/conversations list response."""

    model_config = ConfigDict(extra="allow")

    id: str
    sessionId: str
    siteId: str | None = None
    businessName: str | None = None
    isVoice: bool
    satisfaction: int | None = None
    score: float | None = None
    metrics: QaMetrics | None = None
    createdAt: datetime
    updatedAt: datetime

    @field_validator("metrics", mode="before")
    @classmethod
    def _coerce_metrics(cls, v):
        # Handover doc shape was list[QaTurnMetric]; live shape wraps in {turns:[]}.
        # Normalise the bare-list form into a QaMetrics container.
        if isinstance(v, list):
            return {"turns": v}
        return v


class QaConversation(QaConversationSummary):
    """Full row returned by /api/qa/conversations/<id>."""

    messages: list[QaMessage] = Field(default_factory=list)


class QaConversationList(BaseModel):
    ok: bool
    count: int
    nextCursor: str | None = None
    conversations: list[QaConversationSummary] = Field(default_factory=list)


class QaConversationEnvelope(BaseModel):
    ok: bool
    conversation: QaConversation


class QaHealth(BaseModel):
    ok: bool
    service: str
    serverTime: datetime
