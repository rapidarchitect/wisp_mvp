"""Unit tests for follow-up persistence helpers."""

from app.db.tenant import TenantDB, init_tenant_db
from app.services.followups import (
    get_followups_for_answer,
    insert_followups,
    save_followup_response,
)


async def _seed_db(db: TenantDB) -> int:
    """Seed a user, version, domain, question, and answer. Return answer_id."""
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("c@test.app.wisp.llc", "hash", '["contributor"]', "active", 0, 1),
    )
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    user_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.app.wisp.llc",)))[
        0
    ]
    version_id = (await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1"))[0]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "assigned"),
    )
    await db.commit()
    domain_id = (await db.fetchone("SELECT id FROM domains WHERE code = ?", ("AC",)))[0]
    await db.execute(
        "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (domain_id, "Q1", "yes_no", "seeded", 1, 1),
    )
    await db.commit()
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[
        0
    ]
    cursor = await db.execute(
        "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) "
        "VALUES (?, ?, ?, ?, ?)",
        (question_id, user_id, "yes", 0, "pending"),
    )
    await db.commit()
    return cursor.lastrowid


async def test_insert_and_get_followups(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    answer_id = await _seed_db(db)

    rows = await insert_followups(db, answer_id=answer_id, texts=["What?", "Why?", "When?"])
    assert len(rows) == 3
    assert rows[0]["position"] == 1

    loaded = await get_followups_for_answer(db, answer_id=answer_id)
    assert [r["text"] for r in loaded] == ["What?", "Why?", "When?"]
    await db.close()


async def test_truncates_to_three(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    answer_id = await _seed_db(db)

    rows = await insert_followups(db, answer_id=answer_id, texts=["1", "2", "3", "4", "5"])
    assert len(rows) == 3
    assert rows[-1]["position"] == 3
    await db.close()


async def test_save_response_trims(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    answer_id = await _seed_db(db)
    await insert_followups(db, answer_id=answer_id, texts=["Q1"])
    followup_id = (await db.fetchone("SELECT id FROM followups WHERE answer_id = ?", (answer_id,)))[
        0
    ]

    updated = await save_followup_response(db, followup_id=followup_id, response_text="  A1  ")
    assert updated["response_text"] == "A1"
    assert (await get_followups_for_answer(db, answer_id=answer_id))[0]["response_text"] == "A1"
    await db.close()
