"""Unit tests for the website -> siteId mapping (C10)."""

from __future__ import annotations

import pytest

from backend.db import (
    get_or_create,
    list_websites,
    normalize_url,
    set_site_id,
    upsert_website,
)


def test_normalize_variants_collapse_to_one_host():
    assert normalize_url("webwaala.com") == "webwaala.com"
    assert normalize_url("https://www.webwaala.com/") == "webwaala.com"
    assert normalize_url("  HTTP://WebWaala.com:443/path?x=1 ") == "webwaala.com"


def test_normalize_empty_raises():
    with pytest.raises(ValueError):
        normalize_url("   ")


def test_get_or_create_dedups_on_normalized_url(test_db):
    a = get_or_create("webwaala.com")
    b = get_or_create("https://www.webwaala.com/")  # different scheme + www + slash
    assert a.id == b.id
    assert len(list_websites()) == 1  # no duplicate row


def test_upsert_and_set_site_id_update_same_row(test_db):
    upsert_website("fftechsaas.xyz")
    set_site_id("https://fftechsaas.xyz/", "site-123")
    rows = list_websites()
    assert len(rows) == 1
    assert rows[0].url == "fftechsaas.xyz"
    assert rows[0].site_id == "site-123"


def test_set_site_id_empty_is_noop(test_db):
    upsert_website("x.com")
    set_site_id("x.com", "   ")
    assert list_websites()[0].site_id is None


def test_list_websites_most_recently_used_first(test_db):
    get_or_create("a.com")
    get_or_create("b.com")
    get_or_create("a.com")  # bumps a.com's last_used_at
    urls = [w.url for w in list_websites()]
    assert urls[0] == "a.com"
    assert set(urls) == {"a.com", "b.com"}
