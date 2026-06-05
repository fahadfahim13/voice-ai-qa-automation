"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

import backend.settings as settings_mod
from backend import db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Point the app DB at a fresh temp-file SQLite for the duration of a test.

    Tmp-file (not ``:memory:``) so the same DB is visible across separate
    connections/sessions within the test.
    """
    url = f"sqlite:///{(tmp_path / 'qa.db').as_posix()}"
    monkeypatch.setenv("QA_DB_URL", url)
    monkeypatch.setattr(settings_mod, "_settings", None)  # reset cached Settings
    db.reset_engine()
    db.init_db()
    yield
    db.reset_engine()
