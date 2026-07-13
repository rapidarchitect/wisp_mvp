"""Router tests for the domain assignment API."""

import asyncio
import sqlite3
from importlib import reload

import orjson
import pyotp
import pytest
from fastapi.testclient import TestClient

from app import config as app_config
from app import main as app_main
from app.db.control import init_control_db
from app.db.tenant import get_tenant_db, init_tenant_db
from app.services.auth import hash_password
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


async def _seed_version_and_domain(db):
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    version_id = (await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1"))[0]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "ready"),
    )
    await db.commit()


async def _seed_user(db, email, password, roles):
    secret = generate_totp_secret()
    cur = await db.execute(
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
            orjson.dumps(roles),
            "active",
            secret,
            1,
            0,
        ),
    )
    await db.commit()
    return cur.lastrowid, secret


def _login(client, email, password, secret):
    totp = pyotp.TOTP(secret)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "totp_code": totp.now()},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def auth_client(client, tmp_path):
    """Return (client, admin_headers, contributor_headers, reviewer_headers)."""

    async def _seed():
        db = await get_tenant_db(tmp_path, "acme")
        try:
            await _seed_version_and_domain(db)
            _, admin_secret = await _seed_user(
                db, "admin@acme.app.wisp.llc", "SecurePass123!", ["admin"]
            )
            _, contributor_secret = await _seed_user(
                db, "contributor@acme.app.wisp.llc", "SecurePass123!", ["contributor"]
            )
            _, reviewer_secret = await _seed_user(
                db, "reviewer@acme.app.wisp.llc", "SecurePass123!", ["reviewer"]
            )
            return admin_secret, contributor_secret, reviewer_secret
        finally:
            await db.close()

    admin_secret, contributor_secret, reviewer_secret = asyncio.run(_seed())

    return (
        client,
        _login(client, "admin@acme.app.wisp.llc", "SecurePass123!", admin_secret),
        _login(client, "contributor@acme.app.wisp.llc", "SecurePass123!", contributor_secret),
        _login(client, "reviewer@acme.app.wisp.llc", "SecurePass123!", reviewer_secret),
    )


def test_admin_assign_domain(auth_client):
    """Admin POST /domains/{code}/assign returns 200 and assignment record."""
    client, admin_headers, _, _ = auth_client
    response = client.post(
        "/domains/AC/assign",
        headers=admin_headers,
        json={
            "contributor_email": "contributor@acme.app.wisp.llc",
            "reviewer_email": "reviewer@acme.app.wisp.llc",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "AC"
    assert data["contributor_email"] == "contributor@acme.app.wisp.llc"
    assert data["reviewer_email"] == "reviewer@acme.app.wisp.llc"


def test_contributor_cannot_assign_domain(auth_client):
    """Contributor calling POST /domains/{code}/assign returns 401 or 403."""
    client, _, contributor_headers, _ = auth_client
    response = client.post(
        "/domains/AC/assign",
        headers=contributor_headers,
        json={
            "contributor_email": "contributor@acme.app.wisp.llc",
            "reviewer_email": "reviewer@acme.app.wisp.llc",
        },
    )
    assert response.status_code in (401, 403)


def test_list_my_assignments(auth_client):
    """GET /domains/assigned for contributor returns only their assigned domains."""
    client, admin_headers, contributor_headers, reviewer_headers = auth_client
    client.post(
        "/domains/AC/assign",
        headers=admin_headers,
        json={
            "contributor_email": "contributor@acme.app.wisp.llc",
            "reviewer_email": "reviewer@acme.app.wisp.llc",
        },
    )

    response = client.get("/domains/assigned", headers=contributor_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "AC"
    assert data[0]["role"] == "contributor"

    response = client.get("/domains/assigned", headers=reviewer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "reviewer"


def test_list_unassigned_domains(auth_client):
    """GET /domains/unassigned for admin returns unassigned domains."""
    client, admin_headers, _, _ = auth_client
    response = client.get("/domains/unassigned", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert any(item["code"] == "AC" for item in data)


def test_non_admin_cannot_list_unassigned_domains(auth_client):
    """A non-admin user calling GET /domains/unassigned receives a 403."""
    client, _, contributor_headers, _ = auth_client
    response = client.get("/domains/unassigned", headers=contributor_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_unauthenticated_cannot_list_assigned_domains(auth_client):
    """An unauthenticated caller calling GET /domains/assigned receives a 401."""
    client, _, _, _ = auth_client
    response = client.get("/domains/assigned", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"
