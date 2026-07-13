"""Tests for the authentication service."""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.db.tenant import get_tenant_db, init_tenant_db
from app.exceptions import ValidationError
from app.services.auth import (
    create_session,
    create_user,
    get_user_by_email,
    get_user_from_session,
    hash_password,
    is_account_locked,
    record_failed_login,
    reset_failed_attempts,
    validate_password,
    verify_password,
)


@pytest.fixture
async def tenant_db(tmp_path):
    """An initialized tenant database in a temporary directory."""
    await init_tenant_db(tmp_path, "acme")
    db = await get_tenant_db(tmp_path, "acme")
    yield db
    await db.close()


def test_hash_and_verify_password():
    """Argon2id hashes verify correctly and reject wrong passwords."""
    hashed = hash_password("CorrectHorseBatteryStaple")
    assert verify_password("CorrectHorseBatteryStaple", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_validate_password_enforces_minimum_length():
    """Passwords shorter than 12 characters are rejected."""
    validate_password("Exactly12!!!")  # boundary: 12 chars
    with pytest.raises(ValidationError):
        validate_password("short11")


async def test_create_user_hashes_password(tenant_db):
    """create_user stores an Argon2id hash, not plaintext."""
    user_id = await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    assert user_id is not None

    row = await tenant_db.fetchone("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    assert row["password_hash"] != "CorrectHorseBatteryStaple"
    assert verify_password("CorrectHorseBatteryStaple", row["password_hash"]) is True


async def test_get_user_by_email(tenant_db):
    """get_user_by_email returns the user dict or None."""
    await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])

    user = await get_user_by_email(tenant_db, "a@acme.com")
    assert user is not None
    assert user["email"] == "a@acme.com"
    assert user["roles"] == ["admin"]

    missing = await get_user_by_email(tenant_db, "missing@acme.com")
    assert missing is None


async def test_record_failed_login_increments_counter(tenant_db):
    """Each failed login increments failed_attempts."""
    await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    user = await get_user_by_email(tenant_db, "a@acme.com")

    await record_failed_login(tenant_db, user)
    user = await get_user_by_email(tenant_db, "a@acme.com")
    assert user["failed_attempts"] == 1
    assert user["locked_until"] is None


async def test_account_locks_after_five_failures(tenant_db):
    """C-02: five failures lock the account for 15 minutes."""
    await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    user = await get_user_by_email(tenant_db, "a@acme.com")

    for _ in range(5):
        await record_failed_login(tenant_db, user)
        user = await get_user_by_email(tenant_db, "a@acme.com")

    assert user["failed_attempts"] == 5
    assert user["locked_until"] is not None
    locked_until = datetime.fromisoformat(user["locked_until"])
    now = datetime.now(UTC)
    assert timedelta(minutes=14) < (locked_until - now) < timedelta(minutes=16)
    assert await is_account_locked(user) is True


async def test_lockout_expires_after_15_minutes(tenant_db):
    """C-02: is_account_locked returns False once the lockout window passes."""
    await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    user = await get_user_by_email(tenant_db, "a@acme.com")

    for _ in range(5):
        await record_failed_login(tenant_db, user)
        user = await get_user_by_email(tenant_db, "a@acme.com")

    future = datetime.now(UTC) + timedelta(minutes=16)
    with freeze_time(future):
        assert await is_account_locked(user, now=future) is False


async def test_reset_failed_attempts_clears_lockout(tenant_db):
    """A successful login clears failed attempts and lockout."""
    await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    user = await get_user_by_email(tenant_db, "a@acme.com")

    for _ in range(5):
        await record_failed_login(tenant_db, user)
        user = await get_user_by_email(tenant_db, "a@acme.com")

    await reset_failed_attempts(tenant_db, user["id"])
    user = await get_user_by_email(tenant_db, "a@acme.com")
    assert user["failed_attempts"] == 0
    assert user["locked_until"] is None


async def test_create_session_issued_and_expires_in_8_hours(tenant_db):
    """C-03: sessions expire exactly 8 hours after issue."""
    user_id = await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])

    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    with freeze_time(now):
        token = await create_session(tenant_db, user_id, now=now)

    assert isinstance(token, str)
    assert len(token) > 0

    row = await tenant_db.fetchone(
        "SELECT issued_at, expires_at FROM sessions WHERE token = ?",
        (token,),
    )
    assert datetime.fromisoformat(row["issued_at"]) == now
    assert datetime.fromisoformat(row["expires_at"]) == now + timedelta(hours=8)


async def test_get_user_from_session_returns_active_user(tenant_db):
    """get_user_from_session resolves a valid token to the user."""
    user_id = await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    now = datetime.now(UTC)
    token = await create_session(tenant_db, user_id, now=now)

    session_user = await get_user_from_session(tenant_db, token, now=now)
    assert session_user is not None
    assert session_user["email"] == "a@acme.com"


async def test_get_user_from_session_rejects_expired_token(tenant_db):
    """C-03: tokens past expiry return None."""
    user_id = await create_user(tenant_db, "a@acme.com", "CorrectHorseBatteryStaple", ["admin"])
    now = datetime.now(UTC)
    token = await create_session(tenant_db, user_id, now=now)

    future = now + timedelta(hours=8, minutes=1)
    with freeze_time(future):
        session_user = await get_user_from_session(tenant_db, token, now=future)
    assert session_user is None


async def test_get_user_from_session_rejects_unknown_token(tenant_db):
    """An unknown token returns None."""
    session_user = await get_user_from_session(tenant_db, "not-a-token")
    assert session_user is None
