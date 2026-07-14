"""Unit tests for the answer service."""

import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import TenantDB, init_tenant_db
from app.exceptions import AuthorizationError as ForbiddenError
from app.exceptions import NotFoundError
from app.services.answers import get_domain_progress, save_answer, save_followup_response


async def _seed_db(db: TenantDB):
    """Seed a contributor, reviewer, version, domain, and two questions."""
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("c@test.app.wisp.llc", "hash", '["contributor"]', "active", 0, 1),
    )
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("r@test.app.wisp.llc", "hash", '["reviewer"]', "active", 0, 1),
    )
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    contributor_id = (
        await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.app.wisp.llc",))
    )[0]
    reviewer_id = (
        await db.fetchone("SELECT id FROM users WHERE email = ?", ("r@test.app.wisp.llc",))
    )[0]
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
    await db.execute(
        "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (domain_id, "Q2", "yes_no", "seeded", 1, 2),
    )
    await db.commit()
    await db.execute(
        "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)",
        (domain_id, contributor_id, reviewer_id),
    )
    await db.commit()
    q1 = (
        await db.fetchone(
            "SELECT id FROM questions WHERE domain_id = ? AND position = 1", (domain_id,)
        )
    )[0]
    q2 = (
        await db.fetchone(
            "SELECT id FROM questions WHERE domain_id = ? AND position = 2", (domain_id,)
        )
    )[0]
    return contributor_id, reviewer_id, domain_id, q1, q2


async def test_save_answer_creates_followups(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, _ = await _seed_db(db)

    result = await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q1,
        value="yes",
        llm=FakeLLM(default="1. Why?\n2. How?"),
    )
    assert result["value"] == "yes"
    assert result["followups_state"] == "pending"
    assert len(result["followups"]) == 2
    await db.close()


async def test_skip_answer_blocks_submit_ready(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, q2 = await _seed_db(db)

    await save_answer(
        db, contributor_id=contributor_id, question_id=q1, value="yes", llm=FakeLLM(default="")
    )
    await save_answer(
        db, contributor_id=contributor_id, question_id=q2, skipped=True, llm=FakeLLM(default="")
    )
    progress = await get_domain_progress(db, user_id=contributor_id, code="AC")
    assert progress["submit_ready"] is False
    await db.close()


async def test_answer_without_followups_is_not_submit_ready(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, q2 = await _seed_db(db)

    await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q1,
        value="yes",
        llm=FakeLLM(default="1. Why?"),
    )
    await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q2,
        value="no",
        llm=FakeLLM(default="1. How?"),
    )
    progress = await get_domain_progress(db, user_id=contributor_id, code="AC")
    assert progress["submit_ready"] is False
    await db.close()


async def test_complete_followups_make_submit_ready(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, q2 = await _seed_db(db)

    answer = await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q1,
        value="yes",
        llm=FakeLLM(default="1. Why?"),
    )
    await save_followup_response(
        db,
        contributor_id=contributor_id,
        followup_id=answer["followups"][0]["id"],
        response_text="Because.",
    )
    await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q2,
        value="no",
        llm=FakeLLM(default=""),
    )
    progress = await get_domain_progress(db, user_id=contributor_id, code="AC")
    assert progress["submit_ready"] is True
    await db.close()


async def test_waived_followups_make_submit_ready_on_ai_failure(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, q2 = await _seed_db(db)

    result = await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q1,
        value="yes",
        llm=FakeLLM(fail=True),
    )
    assert result["followups_state"] == "waived"
    await save_answer(
        db,
        contributor_id=contributor_id,
        question_id=q2,
        value="no",
        llm=FakeLLM(default=""),
    )
    progress = await get_domain_progress(db, user_id=contributor_id, code="AC")
    assert progress["submit_ready"] is True
    await db.close()


async def test_cannot_answer_other_contributors_question(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, q1, _ = await _seed_db(db)

    with pytest.raises(ForbiddenError):
        await save_answer(db, contributor_id=999, question_id=q1, value="yes")
    await db.close()


async def test_cannot_answer_unknown_question(tmp_path):
    db = await init_tenant_db(tmp_path, "test")
    contributor_id, _, _, _, _ = await _seed_db(db)

    with pytest.raises(NotFoundError):
        await save_answer(db, contributor_id=contributor_id, question_id=999, value="yes")
    await db.close()
