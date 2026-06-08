"""SQLAlchemy engine + session factory for the dashboard DB (C9).

The repo's first database — deliberately generic and minimal so C10 can add more
models on the same ``Base``. The SQLite file lives under ``reports/`` (gitignored);
override the URL via ``QA_DB_URL``. No Alembic in v1 — ``init_db()`` just creates
the schema; migrations are a future step once the schema starts evolving.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

# Serialize schema creation: Streamlit re-runs ``main()`` (and thus ``init_db()``)
# on every rerun across multiple server threads/sessions that share the cached
# engine. Without this, two threads can both pass ``create_all``'s checkfirst and
# race to ``CREATE TABLE`` the first time a new table is added — the loser raises
# "table already exists".
_init_lock = threading.Lock()
_initialized = False


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
    global _engine, _SessionLocal, _initialized
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _initialized = False  # next init_db() must recreate schema on the new DB


def init_db() -> None:
    """Create the schema if missing (idempotent + thread-safe).

    Ensures the SQLite dir exists. Guarded by ``_init_lock`` so concurrent
    Streamlit reruns don't race on ``create_all`` the first time a new table is
    added; a benign "already exists" from a cross-process race is swallowed.
    """
    global _initialized
    from backend.db import models  # noqa: F401  — register mappers on Base

    url = get_settings().qa_db_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    with _init_lock:
        if _initialized:
            return
        try:
            Base.metadata.create_all(get_engine())
        except OperationalError as exc:  # lost a cross-process create race → already there
            if "already exists" not in str(exc):
                raise
        _ensure_additive_columns()
        _initialized = True


# Columns added to existing tables after v1 shipped. ``create_all`` only creates
# missing *tables*, never missing *columns*, so for a DB that predates the column
# we ALTER it in (SQLite supports cheap ADD COLUMN). No Alembic in v1.
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {"name": "VARCHAR(255)"},
}


def _ensure_additive_columns() -> None:
    """Add post-v1 columns to pre-existing tables (SQLite only; no-op otherwise)."""
    from sqlalchemy import inspect, text

    eng = get_engine()
    if not get_settings().qa_db_url.startswith("sqlite"):
        return
    insp = inspect(eng)
    existing_tables = set(insp.get_table_names())
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in columns.items():
            if col not in present:
                with eng.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


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
