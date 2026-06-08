"""Unit tests for self-service signup + profile (register/change-pw/update/validate)."""

from __future__ import annotations

import pytest

from backend.db import User, get_session
from backend.report import auth


# --------------------------------------------------------------------------- #
# signup_error — pure validation (no DB)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("email", "pw", "confirm", "expected_ok"),
    [
        ("a@b.com", "longenough", "longenough", True),
        ("bad-email", "longenough", "longenough", False),  # no @/domain
        ("a@b.com", "short", "short", False),  # < MIN_PASSWORD_LEN
        ("a@b.com", "longenough", "different", False),  # mismatch
    ],
)
def test_signup_error(email, pw, confirm, expected_ok):
    assert (auth.signup_error(email, pw, confirm) is None) is expected_ok


# --------------------------------------------------------------------------- #
# register_user
# --------------------------------------------------------------------------- #
def test_register_creates_active_user(test_db):
    user = auth.register_user("New@X.com", "pw12345678", name="  Neo  ")
    assert user is not None
    assert user.email == "new@x.com"  # normalized
    assert user.name == "Neo"  # trimmed
    assert user.is_active is True
    # the new account can authenticate immediately (open self-signup)
    assert auth.authenticate("new@x.com", "pw12345678") is not None


def test_register_blank_name_is_none(test_db):
    user = auth.register_user("x@y.com", "pw12345678", name="   ")
    assert user is not None and user.name is None


def test_register_duplicate_email_rejected(test_db):
    assert auth.register_user("dup@x.com", "pw12345678") is not None
    assert auth.register_user("DUP@x.com", "other12345") is None  # case-insensitive dup


# --------------------------------------------------------------------------- #
# change_password
# --------------------------------------------------------------------------- #
def test_change_password_requires_correct_current(test_db):
    auth.register_user("c@x.com", "oldpassword")
    assert auth.change_password("c@x.com", "wrong", "newpassword") is False
    assert auth.change_password("c@x.com", "oldpassword", "newpassword") is True
    # old no longer works; new does
    assert auth.authenticate("c@x.com", "oldpassword") is None
    assert auth.authenticate("c@x.com", "newpassword") is not None


def test_change_password_unknown_user(test_db):
    assert auth.change_password("nobody@x.com", "x", "newpassword") is False


# --------------------------------------------------------------------------- #
# update_profile
# --------------------------------------------------------------------------- #
def test_update_profile_sets_name(test_db):
    auth.register_user("p@x.com", "pw12345678")
    user = auth.update_profile("p@x.com", name="Trinity")
    assert user is not None and user.name == "Trinity"
    with get_session() as s:
        from sqlalchemy import select

        row = s.scalars(select(User).where(User.email == "p@x.com")).first()
        assert row.name == "Trinity"


def test_update_profile_clear_name(test_db):
    auth.register_user("q@x.com", "pw12345678", name="Morpheus")
    user = auth.update_profile("q@x.com", name="")
    assert user is not None and user.name is None
