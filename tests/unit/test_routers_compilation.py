"""Router tests for compilation and submission endpoints."""

from __future__ import annotations

import sqlite3

from app.ai.fakes import FakeLLM


def test_compile_requires_auth(client):
    response = client.post("/domains/AC/compile")
    assert response.status_code == 401


def test_compile_and_submit(client, data_dir, provisioned_user, session_token):
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", ("AC",)).fetchone()[0]
        conn.execute(
            "UPDATE domains SET status = 'assigned' WHERE id = ?",
            (domain_id,),
        )
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
        conn.commit()
    finally:
        conn.close()

    import app.crews.compiler_crew as compiler_crew

    compiler_crew.create_llm = lambda _provider=None: FakeLLM(default="Narrative text.")

    compile_resp = client.post(
        "/domains/AC/compile",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert compile_resp.status_code == 200
    assert compile_resp.json()["narrative_text"]

    submit_resp = client.post(
        "/domains/AC/submit",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "in_review"
