"""Router tests for the notifications API."""

import asyncio
import json
import sqlite3
from importlib import reload

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import config as app_config
from app import main as app_main
from app.db.control import init_control_db
from app.db.tenant import get_tenant_db, init_tenant_db
from app.services.auth import hash_password
from app.services.notifications import notify
from app.services.totp import generate_totp_secret


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
