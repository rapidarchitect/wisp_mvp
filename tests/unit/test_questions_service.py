"""Unit tests for question management services."""

import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError, ValidationError
from app.services.questions import (
    add_question,
    disable_question,
    edit_question,
    regenerate_domain_questions,
    reinstate_question,
)


async def _seed_domain(db):
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
    return (await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0]


async def _seed_questions(db, domain_id, count: int):
    for i in range(count):
        await db.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, f"Q{i + 1}?", "yes_no", "seeded", 1, i),
        )
    await db.commit()


async def _first_question_id(db, domain_id):
    row = await db.fetchone(
        "SELECT id FROM questions WHERE domain_id = ?",
        (domain_id,),
    )
    return row[0]


async def test_add_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)

    result = await add_question(
        db,
        domain_id=domain_id,
        text="  Custom question?  ",
    )

    assert result["origin"] == "admin"
    assert result["enabled"] is True
    count = (
        await db.fetchone(
            "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
            (domain_id,),
        )
    )[0]
    assert count == 6
    await db.close()


async def test_add_question_exceeds_max(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 10)

    with pytest.raises(ValidationError) as exc:
        await add_question(db, domain_id=domain_id, text="Extra?")

    assert exc.value.code == "too_many_questions"
    await db.close()


async def test_edit_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = await _first_question_id(db, domain_id)

    result = await edit_question(db, question_id=question_id, text="Updated text?")

    assert result["text"] == "Updated text?"
    text = (await db.fetchone("SELECT text FROM questions WHERE id = ?", (question_id,)))[0]
    assert text == "Updated text?"
    await db.close()


async def test_disable_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 6)
    question_id = (
        await db.fetchone(
            "SELECT id FROM questions WHERE domain_id = ? AND origin = 'seeded'",
            (domain_id,),
        )
    )[0]

    result = await disable_question(db, question_id=question_id)

    assert result["enabled"] is False
    enabled = (
        await db.fetchone(
            "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
            (domain_id,),
        )
    )[0]
    assert enabled == 5
    await db.close()


async def test_disable_question_blocked_by_minimum(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = await _first_question_id(db, domain_id)

    with pytest.raises(ValidationError) as exc:
        await disable_question(db, question_id=question_id)

    assert exc.value.code == "minimum_questions"
    await db.close()


async def test_reinstate_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = await _first_question_id(db, domain_id)
    await db.execute("UPDATE questions SET enabled = 0 WHERE id = ?", (question_id,))
    await db.commit()

    result = await reinstate_question(db, question_id=question_id)

    assert result["enabled"] is True
    await db.close()


async def test_reinstate_question_exceeds_max(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 11)
    question_id = await _first_question_id(db, domain_id)
    await db.execute("UPDATE questions SET enabled = 0 WHERE id = ?", (question_id,))
    await db.commit()

    with pytest.raises(ValidationError) as exc:
        await reinstate_question(db, question_id=question_id)

    assert exc.value.code == "too_many_questions"
    await db.close()


async def test_regenerate_domain_questions(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    old_ids = {
        r[0]
        for r in await db.fetchall("SELECT id FROM questions WHERE domain_id = ?", (domain_id,))
    }
    llm = FakeLLM(
        default='{"questions": ['
        '{"text": "A?"}, {"text": "B?"}, {"text": "C?"}, '
        '{"text": "D?"}, {"text": "E?"}, {"text": "F?"}'
        "]}"
    )

    result = await regenerate_domain_questions(db, domain_id=domain_id, llm=llm)

    assert result["seeded"] == 6
    assert result["status"] == "ready"
    new_ids = {
        r[0]
        for r in await db.fetchall("SELECT id FROM questions WHERE domain_id = ?", (domain_id,))
    }
    assert not old_ids & new_ids
    await db.close()


async def test_regenerate_domain_questions_blocked_by_answers(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("c@acme.app.wisp.llc", "hash", '["contributor"]', "active", 0, 0),
    )
    await db.commit()
    question_id = await _first_question_id(db, domain_id)
    user_id = (
        await db.fetchone(
            "SELECT id FROM users WHERE email = ?",
            ("c@acme.app.wisp.llc",),
        )
    )[0]
    await db.execute(
        "INSERT INTO answers (question_id, contributor_id, value, skipped) VALUES (?, ?, ?, ?)",
        (question_id, user_id, "yes", 0),
    )
    await db.commit()

    with pytest.raises(ConflictError) as exc:
        await regenerate_domain_questions(db, domain_id=domain_id)

    assert exc.value.code == "domain_has_answers"
    await db.close()
