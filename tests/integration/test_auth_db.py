"""Integration: auth DB schema + manage_users CLI + end-to-end authenticate."""

from __future__ import annotations

from sqlalchemy import inspect
from typer.testing import CliRunner

import backend.settings as settings_mod
from backend import db
from backend.report.auth import authenticate
from scripts.manage_users import app

runner = CliRunner()


def _use_temp_db(tmp_path, monkeypatch) -> None:
    url = f"sqlite:///{(tmp_path / 'qa.db').as_posix()}"
    monkeypatch.setenv("QA_DB_URL", url)
    monkeypatch.setattr(settings_mod, "_settings", None)
    db.reset_engine()


def test_init_db_creates_users_table(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    db.init_db()
    assert "users" in inspect(db.get_engine()).get_table_names()


def test_create_user_then_authenticate(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    r = runner.invoke(app, ["create-user", "--email", "Cli@X.com", "--password", "pw123456"])
    assert r.exit_code == 0, r.output

    # End-to-end: the CLI-created (lower-cased) user authenticates.
    assert authenticate("cli@x.com", "pw123456") is not None


def test_duplicate_email_rejected_cleanly(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)

    assert runner.invoke(app, ["create-user", "--email", "dup@x.com", "--password", "pw123456"]).exit_code == 0
    r = runner.invoke(app, ["create-user", "--email", "dup@x.com", "--password", "pw123456"])
    assert r.exit_code != 0
    assert "already exists" in r.output
    assert "Traceback" not in r.output
