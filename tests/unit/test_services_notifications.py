"""Unit tests for the notification service."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from app.db.tenant import init_tenant_db
from app.exceptions import NotFoundError, ValidationError
from app.services.email_backends import clear_sent_messages, get_sent_messages
from app.services.notifications import get_notifications, mark_read, notify


@pytest.fixture(autouse=True)
def _clear_sent_messages():
    """Reset the console email backend before each notification test."""
    clear_sent_messages()


async def _seed_user(db, email="admin@acme.app.wisp.llc"):
    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, "hash", '["admin"]', "active", 0, 0),
    )
    await db.commit()
    return (await db.fetchone("SELECT id FROM users WHERE email = ?", (email,)))[0]


async def test_notify_creates_in_app_row(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app"
    )

    assert result["notification_id"] is not None
    assert result["channel"] == "in_app"
    assert result["sent_at"] is None
    row = await db.fetchone(
        "SELECT type, channel, sent_at FROM notifications WHERE id = ?",
        (result["notification_id"],),
    )
    assert row["type"] == "roles_updated"
    assert row["channel"] == "in_app"
    assert row["sent_at"] is None
    await db.close()


async def test_notify_sends_email(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(
        db,
        user_id=user_id,
        kind="account_deactivated",
        payload={"email": "admin@acme.app.wisp.llc"},
        channel="email",
    )

    assert result["sent_at"] is not None
    messages = get_sent_messages()
    assert len(messages) == 1
    assert messages[0]["to"] == "admin@acme.app.wisp.llc"
    await db.close()


async def test_notify_both_channels(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "contributor"}
    )

    assert result["channel"] == "both"
    assert result["sent_at"] is not None
    row = await db.fetchone(
        "SELECT channel, sent_at FROM notifications WHERE id = ?", (result["notification_id"],)
    )
    assert row["channel"] == "both"
    assert row["sent_at"] is not None
    await db.close()


async def test_notify_unknown_kind(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    with pytest.raises(ValidationError, match="Unknown notification kind"):
        await notify(db, user_id=user_id, kind="not_a_kind", payload={})

    await db.close()


async def test_notify_missing_payload_key(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    with pytest.raises(ValidationError, match="Missing payload key"):
        await notify(db, user_id=user_id, kind="roles_updated", payload={})

    await db.close()


async def test_notify_user_not_found(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")

    with pytest.raises(NotFoundError):
        await notify(db, user_id=999, kind="roles_updated", payload={"roles": "admin"})

    await db.close()


async def test_get_notifications_orders_by_id(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "a"}, channel="in_app"
    )
    await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "b"}, channel="in_app"
    )

    rows = await get_notifications(db, user_id)

    assert [r["payload"] for r in rows] == [{"roles": "b"}, {"roles": "a"}]
    await db.close()


async def test_get_notifications_unread_only(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    r1 = await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "a"}, channel="in_app"
    )
    await mark_read(db, r1["notification_id"], user_id)
    await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "b"}, channel="in_app"
    )

    rows = await get_notifications(db, user_id, unread_only=True)

    assert len(rows) == 1
    assert rows[0]["payload"] == {"roles": "b"}
    await db.close()


async def test_mark_read(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    result = await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app"
    )

    read = await mark_read(db, result["notification_id"], user_id)

    assert read["read_at"] is not None
    row = await db.fetchone(
        "SELECT read_at FROM notifications WHERE id = ?", (result["notification_id"],)
    )
    assert row["read_at"] is not None
    await db.close()


async def test_mark_read_not_owned(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    other_id = await _seed_user(db, email="other@acme.app.wisp.llc")
    result = await notify(
        db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app"
    )

    with pytest.raises(NotFoundError):
        await mark_read(db, result["notification_id"], other_id)

    await db.close()


async def test_ses_backend_send(tmp_path):
    from app.services.email_backends import SESEmailBackend

    backend = SESEmailBackend()
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        await backend.send(to="x@example.com", subject="Hi", body="Hello")

    mock_client.send_email.assert_called_once()


async def test_ses_client_is_cached():
    """SESEmailBackend reuses the boto3 client across sends."""
    from app.services.email_backends import SESEmailBackend

    backend = SESEmailBackend()
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client) as mock_boto:
        await backend.send(to="a@example.com", subject="A", body="body")
        await backend.send(to="b@example.com", subject="B", body="body")

    mock_boto.assert_called_once()
    assert backend._client is mock_client
    assert mock_client.send_email.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "rejected"}},
            "SendEmail",
        ),
        BotoCoreError(msg="SES failure"),
    ],
)
async def test_ses_send_error_wrapped(exception):
    """SES client exceptions are wrapped in ExternalServiceError."""
    from app.exceptions import ExternalServiceError
    from app.services.email_backends import SESEmailBackend

    backend = SESEmailBackend()
    mock_client = MagicMock()
    mock_client.send_email.side_effect = exception
    with patch("boto3.client", return_value=mock_client), pytest.raises(ExternalServiceError):
        await backend.send(to="x@example.com", subject="Hi", body="Hello")


def test_get_email_backend_singleton(monkeypatch):
    """get_email_backend returns the same instance on repeated calls."""
    from app.services.email_backends import (
        ConsoleEmailBackend,
        get_email_backend,
        reset_email_backend,
    )

    reset_email_backend()
    monkeypatch.setattr("app.services.email_backends.settings.email_backend", "console")
    b1 = get_email_backend()
    b2 = get_email_backend()
    assert b1 is b2
    assert isinstance(b1, ConsoleEmailBackend)
    reset_email_backend()
