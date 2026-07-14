"""Unit tests for the questionnaire router."""

import asyncio
import sqlite3
from importlib import reload

import orjson
import pyotp
import pytest
from fastapi.testclient import TestClient

from app import config as app_config
from app import main as app_main
from app.ai.fakes import FakeLLM
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
        ("AC", "Access Control", version_id, "assigned"),
    )
    await db.commit()
    return version_id


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
def auth_client(client, tmp_path, monkeypatch):
    """Return (client, contributor_headers, reviewer_headers, domain_id, q1_id)."""

    async def _seed():
        db = await get_tenant_db(tmp_path, "acme")
        try:
            version_id = await _seed_version_and_domain(db)
            contributor_id, contributor_secret = await _seed_user(
                db, "contributor@acme.app.wisp.llc", "SecurePass123!", ["contributor"]
            )
            reviewer_id, reviewer_secret = await _seed_user(
                db, "reviewer@acme.app.wisp.llc", "SecurePass123!", ["reviewer"]
            )
            domain_id = (
                await db.fetchone(
                    "SELECT id FROM domains WHERE code = ? AND wisp_version_id = ?",
                    ("AC", version_id),
                )
            )[0]
            await db.execute(
                """
                INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                VALUES (?, ?, ?)
                """,
                (domain_id, contributor_id, reviewer_id),
            )
            await db.execute(
                """
                INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (domain_id, "Q1", "yes_no", "seeded", 1, 1),
            )
            await db.commit()
            question_id = (await db.fetchone("SELECT last_insert_rowid()"))[0]
            return contributor_secret, reviewer_secret, domain_id, question_id
        finally:
            await db.close()

    contributor_secret, reviewer_secret, domain_id, question_id = asyncio.run(_seed())

    # Ensure follow-up generation is deterministic.
    fake_llm = FakeLLM(default="1. Why?")
    monkeypatch.setattr("app.crews.followup_crew.create_llm", lambda _provider=None: fake_llm)

    return (
        client,
        _login(client, "contributor@acme.app.wisp.llc", "SecurePass123!", contributor_secret),
        _login(client, "reviewer@acme.app.wisp.llc", "SecurePass123!", reviewer_secret),
        domain_id,
        question_id,
    )


def test_progress_requires_auth(client):
    response = client.get("/domains/AC/progress", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_answer_and_progress(auth_client):
    client, contributor_headers, _, _, q1 = auth_client

    response = client.post(
        f"/questions/{q1}/answer",
        json={"value": "yes"},
        headers=contributor_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "yes"
    assert len(data["followups"]) == 1

    followup_id = data["followups"][0]["id"]
    response = client.post(
        f"/followups/{followup_id}/respond",
        json={"response_text": "Because."},
        headers=contributor_headers,
    )
    assert response.status_code == 200

    response = client.get("/domains/AC/progress", headers=contributor_headers)
    assert response.status_code == 200
    progress = response.json()
    assert progress["submit_ready"] is True


def test_skip_blocks_submit_ready(auth_client):
    client, contributor_headers, _, _, q1 = auth_client

    response = client.post(
        f"/questions/{q1}/answer",
        json={"skipped": True},
        headers=contributor_headers,
    )
    assert response.status_code == 200

    response = client.get("/domains/AC/progress", headers=contributor_headers)
    assert response.status_code == 200
    progress = response.json()
    assert progress["submit_ready"] is False
