"""Tests for the password reset service and email backend."""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from app.db.tenant import get_tenant_db, init_tenant_db
from app.exceptions import AuthorizationError
from app.services.auth import create_user, verify_password
from app.services.email_backends import ConsoleEmailBackend, clear_sent_messages, get_sent_messages
from app.services.password_reset import create_reset_token, reset_password, verify_reset_token


@pytest.fixture
async def tenant_db(tmp_path):
    """An initialized tenant database in a temporary directory."""
    await init_tenant_db(tmp_path, "acme")
    db = await get_tenant_db(tmp_path, "acme")
    yield db
    await db.close()


def test_create_and_verify_reset_token():
    """A created token verifies and returns the original user_id."""
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    token = create_reset_token(7, "a@acme.com", now, "secret-key")
    user_id = verify_reset_token(token, "secret-key", now)
    assert user_id == 7


def test_verify_reset_token_rejects_tampered_token():
    """A token with a modified payload is rejected."""
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    token = create_reset_token(7, "a@acme.com", now, "secret-key")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(AuthorizationError):
        verify_reset_token(tampered, "secret-key", now)


def test_verify_reset_token_rejects_expired_token():
    """C-06: a token older than 30 minutes is rejected."""
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    token = create_reset_token(7, "a@acme.com", now, "secret-key")
    future = now + timedelta(minutes=31)
    with freeze_time(future), pytest.raises(AuthorizationError, match="Reset token expired"):
        verify_reset_token(token, "secret-key", future)


def test_verify_reset_token_rejects_wrong_secret():
    """A token signed with a different secret is rejected."""
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    token = create_reset_token(7, "a@acme.com", now, "secret-a")
    with pytest.raises(AuthorizationError):
        verify_reset_token(token, "secret-b", now)


async def test_reset_password_updates_hash(tenant_db):
    """reset_password stores a new Argon2id hash for the user."""
    user_id = await create_user(tenant_db, "a@acme.com", "OldPassword123", ["admin"])
    await reset_password(tenant_db, user_id, "NewPassword456")

    row = await tenant_db.fetchone(
        "SELECT password_hash FROM users WHERE id = ?",
        (user_id,),
    )
    assert verify_password("NewPassword456", row["password_hash"]) is True
    assert verify_password("OldPassword123", row["password_hash"]) is False


async def test_reset_password_rejects_short_password(tenant_db):
    """reset_password enforces the 12-character minimum."""
    user_id = await create_user(tenant_db, "a@acme.com", "OldPassword123", ["admin"])
    from app.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await reset_password(tenant_db, user_id, "short")


async def test_console_email_backend_captures_message():
    """ConsoleEmailBackend stores the message and makes it retrievable."""
    clear_sent_messages()
    backend = ConsoleEmailBackend()
    await backend.send(
        to="a@acme.com",
        subject="Reset",
        body="token=abc123",
    )

    messages = get_sent_messages()
    assert len(messages) == 1
    assert messages[0]["to"] == "a@acme.com"
    assert messages[0]["subject"] == "Reset"
    assert "token=abc123" in messages[0]["body"]
