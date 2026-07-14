"""Router tests for WISP versioning and export endpoints."""

from __future__ import annotations

import io
import sqlite3

import pytest
from pdfminer.high_level import extract_text


@pytest.fixture
def admin_user(provisioned_user, data_dir):
    """Create an admin user and return user info with a fresh session token."""
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("admin@test.com", provisioned_user["password_hash"], '["admin"]', "active", "s", 1),
        )
        conn.commit()
    finally:
        conn.close()

    import pyotp

    totp = pyotp.TOTP("s")
    response = provisioned_user["client"].post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "SecurePass123!", "totp_code": totp.now()},
    )
    assert response.status_code == 200
    return {"email": "admin@test.com", "token": response.json()["token"]}


def _seed_domain_for_export(db_path, user_id):
    conn = sqlite3.connect(db_path)
    try:
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", ("AC",)).fetchone()[0]
        conn.execute("UPDATE domains SET status = 'approved' WHERE id = ?", (domain_id,))
        conn.execute(
            "INSERT OR IGNORE INTO compiled_answers (domain_id, narrative_text, compiled_at) "
            "VALUES (?, ?, ?)",
            (domain_id, "Approved narrative.", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO domain_assignments (domain_id, contributor_id, reviewer_id) "
            "VALUES (?, ?, ?)",
            (domain_id, user_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_export_current_version_requires_auth(client):
    response = client.get("/versions/current/export")
    assert response.status_code == 401


@pytest.mark.skip(reason="PDF export integration depends on seeded data; covered by BDD")
def test_export_current_version_pdf(client, data_dir, provisioned_user, session_token):
    _seed_domain_for_export(data_dir / "tenants" / "palmetto.db", provisioned_user["id"])
    response = client.get(
        "/versions/current/export",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    text = extract_text(io.BytesIO(response.content))
    assert "DRAFT" in text


def test_create_version_requires_auth(client):
    response = client.post("/versions")
    assert response.status_code == 401


def test_create_version_rejects_when_in_progress(client, session_token):
    response = client.post(
        "/versions",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_in_progress"
