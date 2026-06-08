"""ORM models for the dashboard DB (C9).

C9 introduces ``User``; C10 will add more tables on the same ``Base``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.engine import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """A dashboard login. Emails are stored lower-cased and are unique."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User {self.email} active={self.is_active}>"


class Website(Base):
    """An operator-facing website target and its resolved internal siteId (C10).

    ``url`` is the normalized canonical host (see
    :func:`backend.db.websites.normalize_url`) and is the natural key. ``site_id``
    is filled in lazily once the first run resolves the widget's internal siteId.
    """

    __tablename__ = "websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    site_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Website {self.url} site_id={self.site_id}>"
