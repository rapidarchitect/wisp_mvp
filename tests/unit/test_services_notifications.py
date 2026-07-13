"""Unit tests for the notification service."""

import asyncio
import json
import sqlite3
from importlib import reload
from unittest.mock import MagicMock, patch

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import config as app_config
from app import main as app_main
from app.db.control import init_control_db
from app.db.tenant import get_tenant_db, init_tenant_db
from app.exceptions import NotFoundError, ValidationError
from app.services.auth import hash_password
from app.services.email_backends import clear_sent_messages, get_sent_messages
from app.services.notifications import get_notifications, mark_read, notify
from app.services.totp import generate_totp_secret


@pytest.fixture(autouse=True)
def _clear_sent_messages():
    """Reset the console email backend before each notification test."""
    clear_sent_messages()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Return a TestClient for app.main:app wired to a temp provisioned tenant."""
    monkeypatch.setenv("WISPGEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WISPGEN_BASE_DOMAIN", "app.wisp.llc")
    reload(app_config)
    reload(app_main)

    asyncio.run(init_control_db(tmp_path / "control.db"))

    conn = sqlite3.connect(tmp_path / "control.db")
    conn.execute(
        "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
        ("acme", "Acme CPA", "active"),
    )
    conn.commit()
    conn.close()

    asyncio.run(init_tenant_db(tmp_path, "acme"))

    return TestClient(app_main.app, base_url="http://acme.app.wisp.llc")


@pytest.fixture
def auth_client(client, tmp_path):
    """Return (client, auth_headers, user_id) for a logged-in user."""
    password = "SecurePass123!"
    email = "admin@acme.app.wisp.llc"
    secret = generate_totp_secret()

    async def _seed():
        db = await get_tenant_db(tmp_path, "acme")
        try:
            await db.execute(
                """
                INSERT INTO users (
                    email, password_hash, roles, status, totp_secret, totp_enrolled,
                    failed_attempts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    hash_password(password),
                    json.dumps(["admin"]),
                    "active",
                    secret,
                    1,
                    0,
                ),
            )
            await db.commit()
            row = await db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
            return row["id"]
        finally:
            await db.close()

    user_id = asyncio.run(_seed())

    totp = pyotp.TOTP(secret)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "totp_code": totp.now()},
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, user_id


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


def test_list_notifications_endpoint(auth_client, tmp_path):
    """GET /notifications returns the logged-in user's feed."""
    client, headers, user_id = auth_client

    async def _create():
        db = await get_tenant_db(tmp_path, "acme")
        try:
            await notify(
                db,
                user_id=user_id,
                kind="roles_updated",
                payload={"roles": "admin"},
                channel="in_app",
            )
        finally:
            await db.close()

    asyncio.run(_create())

    response = client.get("/notifications", headers=headers)
    assert response.status_code == 200
    feed = response.json()
    assert any(
        item["type"] == "roles_updated" and item["payload"] == {"roles": "admin"} for item in feed
    )


def test_mark_read_endpoint(auth_client, tmp_path):
    """POST /notifications/{id}/read marks a notification as read."""
    client, headers, user_id = auth_client

    async def _create():
        db = await get_tenant_db(tmp_path, "acme")
        try:
            return await notify(
                db,
                user_id=user_id,
                kind="roles_updated",
                payload={"roles": "admin"},
                channel="in_app",
            )
        finally:
            await db.close()

    result = asyncio.run(_create())
    notification_id = result["notification_id"]

    response = client.post(f"/notifications/{notification_id}/read", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["notification_id"] == notification_id
    assert data["read_at"] is not None


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


async def test_ses_send_error_wrapped():
    """SES client exceptions are wrapped in ExternalServiceError."""
    from botocore.exceptions import ClientError

    from app.exceptions import ExternalServiceError
    from app.services.email_backends import SESEmailBackend

    backend = SESEmailBackend()
    mock_client = MagicMock()
    mock_client.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "rejected"}},
        "SendEmail",
    )
    with patch("boto3.client", return_value=mock_client), pytest.raises(ExternalServiceError):
        await backend.send(to="x@example.com", subject="Hi", body="Hello")
