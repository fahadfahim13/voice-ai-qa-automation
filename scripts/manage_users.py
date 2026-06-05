"""User-management CLI for the dashboard auth DB (C9).

    uv run python scripts/manage_users.py create-user --email you@x.com --password ...
    uv run python scripts/manage_users.py list-users
    uv run python scripts/manage_users.py deactivate-user --email you@x.com
    uv run python scripts/manage_users.py reset-password --email you@x.com --password ...

Passwords are bcrypt-hashed before storage; the plaintext is never logged.
"""

from __future__ import annotations

import typer
from loguru import logger
from sqlalchemy import select

from backend.db import User, get_session, init_db
from backend.logging import setup_logging
from backend.report.auth import hash_password

app = typer.Typer(add_completion=False, help="Manage dashboard users.")


def _norm(email: str) -> str:
    return email.strip().lower()


def _setup() -> None:
    setup_logging()
    init_db()


@app.command("create-user")
def create_user(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(..., "--password"),
) -> None:
    """Create a new active user."""
    _setup()
    email = _norm(email)
    with get_session() as s:
        if s.scalars(select(User).where(User.email == email)).first():
            raise typer.BadParameter(f"User already exists: {email}")
        s.add(User(email=email, password_hash=hash_password(password)))
    logger.success("Created user {}", email)


@app.command("list-users")
def list_users() -> None:
    """List all users."""
    _setup()
    with get_session() as s:
        users = s.scalars(select(User).order_by(User.created_at)).all()
    if not users:
        typer.echo("(no users)")
        return
    for u in users:
        typer.echo(
            f"{u.id:>3}  {u.email:<32} active={u.is_active}  created={u.created_at:%Y-%m-%d %H:%M}"
        )


@app.command("deactivate-user")
def deactivate_user(email: str = typer.Option(..., "--email")) -> None:
    """Deactivate a user (they can no longer log in)."""
    _setup()
    email = _norm(email)
    with get_session() as s:
        user = s.scalars(select(User).where(User.email == email)).first()
        if not user:
            raise typer.BadParameter(f"No such user: {email}")
        user.is_active = False
    logger.success("Deactivated {}", email)


@app.command("reset-password")
def reset_password(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(..., "--password"),
) -> None:
    """Set a new password for a user."""
    _setup()
    email = _norm(email)
    with get_session() as s:
        user = s.scalars(select(User).where(User.email == email)).first()
        if not user:
            raise typer.BadParameter(f"No such user: {email}")
        user.password_hash = hash_password(password)
    logger.success("Reset password for {}", email)


if __name__ == "__main__":
    app()
