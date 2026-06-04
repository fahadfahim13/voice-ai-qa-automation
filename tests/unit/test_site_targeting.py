"""Unit tests for siteId targeting helpers (C6, 4e)."""

from __future__ import annotations

from backend.report import site_targeting as st_mod


# --- validate_site_id -------------------------------------------------------
def test_validate_known(monkeypatch):
    monkeypatch.setattr(st_mod, "_fetch_conversations", lambda sid, limit=1: [object()])
    res = st_mod.validate_site_id("qa-judge")
    assert res["status"] == "known"
    assert res["count"] == 1


def test_validate_no_traffic(monkeypatch):
    monkeypatch.setattr(st_mod, "_fetch_conversations", lambda sid, limit=1: [])
    assert st_mod.validate_site_id("brand-new")["status"] == "no_traffic"


def test_validate_unreachable_does_not_raise(monkeypatch):
    def boom(sid, limit=1):
        raise RuntimeError("network down")

    monkeypatch.setattr(st_mod, "_fetch_conversations", boom)
    res = st_mod.validate_site_id("whatever")
    assert res["status"] == "unreachable"
    assert "network down" in res["error"]


def test_validate_empty():
    assert st_mod.validate_site_id("   ")["status"] == "empty"


# --- recent siteIds ---------------------------------------------------------
def test_recent_site_ids_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(st_mod, "_recent_path", lambda: tmp_path / "recent.json")
    assert st_mod.recent_site_ids() == []
    st_mod.remember_site_id("a")
    st_mod.remember_site_id("b")
    st_mod.remember_site_id("a")  # moves to front, deduped
    assert st_mod.recent_site_ids() == ["a", "b"]
    st_mod.remember_site_id("")  # blank ignored
    assert st_mod.recent_site_ids() == ["a", "b"]


# --- url_to_site_id (stretch) ----------------------------------------------
def test_url_scan_blocked_without_token(monkeypatch):
    monkeypatch.delenv(st_mod.ADMIN_TOKEN_ENV, raising=False)
    assert not st_mod.admin_scan_available()
    res = st_mod.url_to_site_id("https://example.com")
    assert "error" in res and "admin" in res["error"].lower()


def test_url_scan_success(monkeypatch):
    monkeypatch.setenv(st_mod.ADMIN_TOKEN_ENV, "tok")
    monkeypatch.setattr(st_mod, "_post_scan", lambda url, token, base: {"siteId": "resolved-site"})
    assert st_mod.admin_scan_available()
    assert st_mod.url_to_site_id("https://example.com") == {"site_id": "resolved-site"}


def test_url_scan_http_error_no_raise(monkeypatch):
    monkeypatch.setenv(st_mod.ADMIN_TOKEN_ENV, "tok")

    def boom(url, token, base):
        raise RuntimeError("502 bad gateway")

    monkeypatch.setattr(st_mod, "_post_scan", boom)
    res = st_mod.url_to_site_id("https://example.com")
    assert "error" in res and "502" in res["error"]


def test_url_scan_missing_siteid(monkeypatch):
    monkeypatch.setenv(st_mod.ADMIN_TOKEN_ENV, "tok")
    monkeypatch.setattr(st_mod, "_post_scan", lambda url, token, base: {"unexpected": 1})
    assert "error" in st_mod.url_to_site_id("https://example.com")
