"""Authentication services: passwords, sessions, and account lockout."""

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.exceptions import ValidationError

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


_argon2 = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _argon2.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        _argon2.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def validate_password(password: str) -> None:
    """Enforce the password policy (minimum 12 characters)."""
    if len(password) < 12:
        raise ValidationError("Password must be at least 12 characters")


async def create_user(
    db: "TenantDB",
    email: str,
    password: str,
    roles: list[str],
    status: str = "active",
) -> int:
    """Create a new user with a hashed password and return the user id."""
    validate_password(password)
    cursor = await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            email,
            hash_password(password),
            json.dumps(roles),
            status,
            0,
            False,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def get_user_by_email(db: "TenantDB", email: str) -> dict | None:
    """Fetch a user row by email, or None if not found."""
    row = await db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
    if row is None:
        return None
    user = dict(row)
    user["roles"] = json.loads(user["roles"])
    return user


async def record_failed_login(db: "TenantDB", user: dict) -> None:
    """Increment failed attempts and lock the account after 5 failures."""
    failed = user["failed_attempts"] + 1
    locked_until = None
    if failed >= 5:
        locked_until = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
    await db.execute(
        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (failed, locked_until, user["id"]),
    )
    await db.commit()


async def is_account_locked(user: dict, now: datetime | None = None) -> bool:
    """Return True if the user's lockout window is still active."""
    if now is None:
        now = datetime.now(UTC)
    locked_until = user.get("locked_until")
    if locked_until is None:
        return False
    return now < datetime.fromisoformat(locked_until)


async def reset_failed_attempts(db: "TenantDB", user_id: int) -> None:
    """Clear failed attempts and lockout timestamp after a successful login."""
    await db.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (user_id,),
    )
    await db.commit()


async def create_session(
    db: "TenantDB",
    user_id: int,
    now: datetime | None = None,
) -> str:
    """Create an 8-hour session and return its token."""
    if now is None:
        now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=8)
    await db.execute(
        """
        INSERT INTO sessions (user_id, token, issued_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, token, now.isoformat(), expires_at.isoformat()),
    )
    await db.commit()
    return token


async def get_user_from_session(
    db: "TenantDB",
    token: str,
    now: datetime | None = None,
) -> dict | None:
    """Return the user for a valid, unexpired session token."""
    if now is None:
        now = datetime.now(UTC)
    row = await db.fetchone(
        """
        SELECT s.expires_at, u.*
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
        """,
        (token,),
    )
    if row is None:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if now >= expires_at:
        return None
    user = dict(row)
    user["roles"] = json.loads(user["roles"])
    return user
