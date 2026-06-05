"""SQLAlchemy engine + session factory for the dashboard DB (C9).

The repo's first database — deliberately generic and minimal so C10 can add more
models on the same ``Base``. The SQLite file lives under ``reports/`` (gitignored);
override the URL via ``QA_DB_URL``. No Alembic in v1 — ``init_db()`` just creates
the schema; migrations are a future step once the schema starts evolving.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazily build + cache the engine from ``settings.qa_db_url``."""
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().qa_db_url
        # SQLite + Streamlit run across threads; allow cross-thread use.
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def reset_engine() -> None:
    """Dispose + forget the cached engine (tests point at a fresh DB)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db() -> None:
    """Create the schema if missing (idempotent). Ensures the SQLite dir exists."""
    from backend.db import models  # noqa: F401  — register mappers on Base

    url = get_settings().qa_db_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine())


@contextmanager
def get_session() -> Iterator[Session]:
    """Transactional session: commits on success, rolls back on error."""
    get_engine()  # ensure _SessionLocal is initialised
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
