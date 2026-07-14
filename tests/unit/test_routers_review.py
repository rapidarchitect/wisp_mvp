"""Router tests for review workflow endpoints."""

from __future__ import annotations

import sqlite3

from app.ai.fakes import FakeLLM


def test_approve_requires_auth(client):
    response = client.post("/domains/AC/approve")
    assert response.status_code == 401


def test_approve_and_defer(client, data_dir, provisioned_user, session_token):
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        # Provision an admin to reassign the domain to the same user as reviewer.
        conn.execute(
            "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("admin@test.com", "x", '["admin"]', "active", "s", 1),
        )
        conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("SELECT id FROM wisp_versions").fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", ("AC",)).fetchone()[0]
        conn.execute("UPDATE domains SET status = 'in_review' WHERE id = ?", (domain_id,))
        conn.execute(
            "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) "
            "VALUES (?, ?, ?)",
            (domain_id, provisioned_user["id"], provisioned_user["id"]),
        )
        conn.execute(
            "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (domain_id, "Q1", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) "
            "VALUES (?, ?, ?, ?, ?)",
            (question_id, provisioned_user["id"], "yes", 0, "complete"),
        )
        conn.execute(
            "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) "
            "VALUES (?, ?, ?)",
            (domain_id, "Compiled.", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    approve_resp = client.post(
        "/domains/AC/approve",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["status"] == "approved"
    assert body["self_review"] is True


def test_revise_domain(client, data_dir, provisioned_user, session_token):
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute("SELECT id FROM wisp_versions").fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", ("AC",)).fetchone()[0]
        conn.execute("UPDATE domains SET status = 'in_review' WHERE id = ?", (domain_id,))
        conn.execute(
            "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) "
            "VALUES (?, ?, ?)",
            (domain_id, provisioned_user["id"], provisioned_user["id"]),
        )
        conn.execute(
            "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (domain_id, "Q1", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) "
            "VALUES (?, ?, ?, ?, ?)",
            (question_id, provisioned_user["id"], "yes", 0, "complete"),
        )
        conn.execute(
            "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) "
            "VALUES (?, ?, ?)",
            (domain_id, "Old.", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    import app.crews.revision_crew as revision_crew

    revision_crew.create_llm = lambda _provider=None: FakeLLM(default="Revised narrative text.")

    revise_resp = client.post(
        "/domains/AC/revise",
        json={"revision_prompt": "Add badge detail"},
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert revise_resp.status_code == 200
    body = revise_resp.json()
    assert body["status"] == "approved"

    conn = sqlite3.connect(path)
    try:
        narrative = conn.execute(
            "SELECT narrative_text FROM compiled_answers WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()[0]
        assert "Revised narrative text." in narrative
    finally:
        conn.close()
