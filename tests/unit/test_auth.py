"""Unit tests for C9 auth — hashing, JWT, and authenticate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from backend.db import User, get_session
from backend.report import auth


def test_hash_and_verify():
    h = auth.hash_password("secret123")
    assert h != "secret123"  # never store plaintext
    assert auth.verify_password("secret123", h) is True
    assert auth.verify_password("wrong", h) is False


def test_token_round_trip():
    token = auth.create_access_token("a@b.com", expires_minutes=5)
    claims = auth.decode_token(token)
    assert claims is not None
    assert claims["sub"] == "a@b.com"


def test_token_wrong_secret_rejected():
    bad = jwt.encode({"sub": "a@b.com"}, "a-different-secret-long-enough-to-be-valid", algorithm="HS256")
    assert auth.decode_token(bad) is None


def test_token_expired_rejected():
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": "a@b.com", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        auth._secret(),
        algorithm="HS256",
    )
    assert auth.decode_token(expired) is None


def test_token_tampered_rejected():
    token = auth.create_access_token("a@b.com")
    assert auth.decode_token(token + "x") is None


def test_decode_none_and_garbage():
    assert auth.decode_token(None) is None
    assert auth.decode_token("not-a-jwt") is None


def test_authenticate(test_db):
    with get_session() as s:
        s.add(User(email="u@x.com", password_hash=auth.hash_password("pw123456")))
        s.add(
            User(
                email="off@x.com",
                password_hash=auth.hash_password("pw123456"),
                is_active=False,
            )
        )

    assert auth.authenticate("U@X.com", "pw123456") is not None  # case-insensitive
    assert auth.authenticate("u@x.com", "wrong") is None
    assert auth.authenticate("off@x.com", "pw123456") is None  # inactive
    assert auth.authenticate("missing@x.com", "pw123456") is None
    assert auth.authenticate("", "pw123456") is None
