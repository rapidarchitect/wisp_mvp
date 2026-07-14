"""Unit tests for compilation and submission service."""

from __future__ import annotations

import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import AuthorizationError, ConflictError
from app.services.compilation import compile_domain, submit_domain


@pytest.fixture
async def db(tmp_path):
    return await init_tenant_db(str(tmp_path), "palmetto")


_INSERT_USER = (
    "INSERT INTO users "
    "(email, password_hash, roles, status, totp_secret, totp_enrolled) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

_INSERT_VERSION = "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)"

_INSERT_DOMAIN = "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)"

_INSERT_ASSIGNMENT = (
    "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)"
)

_INSERT_QUESTION = (
    "INSERT INTO questions "
    "(domain_id, text, answer_type, origin, enabled, position) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

_INSERT_ANSWER = (
    "INSERT INTO answers "
    "(question_id, contributor_id, value, skipped, followups_state) "
    "VALUES (?, ?, ?, ?, ?)"
)


async def _seed_domain(db, *, contributor_id=None, reviewer_id=None, answer_state="complete"):
    if contributor_id is None:
        await db.execute(
            _INSERT_USER,
            ("c@test.com", "x", '["contributor"]', "active", "s", 1),
        )
        row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",))
        contributor_id = row["id"]
    if reviewer_id is None:
        reviewer_id = contributor_id
    await db.execute(_INSERT_VERSION, (1, 1, "in_progress"))
    version_id = (await db.fetchone("SELECT id FROM wisp_versions"))["id"]
    await db.execute(_INSERT_DOMAIN, ("AC", "Access Control", version_id, "assigned"))
    domain_id = (await db.fetchone("SELECT id FROM domains"))["id"]
    await db.execute(
        _INSERT_ASSIGNMENT,
        (domain_id, contributor_id, reviewer_id),
    )
    await db.execute(_INSERT_QUESTION, (domain_id, "Q1", "yes_no", "seeded", 1, 1))
    question_id = (await db.fetchone("SELECT id FROM questions"))["id"]
    await db.execute(
        _INSERT_ANSWER,
        (question_id, contributor_id, "yes", 0, answer_state),
    )
    await db.commit()
    return domain_id, contributor_id, reviewer_id


@pytest.mark.asyncio
async def test_compile_domain_requires_answers(db):
    await db.execute(
        _INSERT_USER,
        ("c@test.com", "x", '["contributor"]', "active", "s", 1),
    )
    row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",))
    contributor_id = row["id"]
    await db.execute(_INSERT_VERSION, (1, 1, "in_progress"))
    version_id = (await db.fetchone("SELECT id FROM wisp_versions"))["id"]
    await db.execute(_INSERT_DOMAIN, ("AC", "Access Control", version_id, "assigned"))
    domain_id = (await db.fetchone("SELECT id FROM domains"))["id"]
    await db.execute(
        _INSERT_ASSIGNMENT,
        (domain_id, contributor_id, contributor_id),
    )
    await db.commit()
    with pytest.raises(ConflictError):
        await compile_domain(db, contributor_id=contributor_id, code="AC")


@pytest.mark.asyncio
async def test_compile_and_submit_flow(db):
    _, contributor_id, _ = await _seed_domain(db)
    compiled = await compile_domain(
        db,
        contributor_id=contributor_id,
        code="AC",
        llm=FakeLLM(default="Narrative text."),
    )
    assert compiled["narrative_text"]
    assert "domain_id" in compiled

    submitted = await submit_domain(db, contributor_id=contributor_id, code="AC")
    assert submitted["status"] == "in_review"


@pytest.mark.asyncio
async def test_compile_domain_blocks_wrong_contributor(db):
    await _seed_domain(db)
    await db.execute(
        _INSERT_USER,
        ("other@test.com", "x", '["contributor"]', "active", "s", 1),
    )
    row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("other@test.com",))
    other_id = row["id"]
    await db.commit()
    with pytest.raises(AuthorizationError):
        await compile_domain(db, contributor_id=other_id, code="AC")


@pytest.mark.asyncio
async def test_compile_domain_blocks_in_review(db):
    domain_id, contributor_id, _ = await _seed_domain(db)
    await db.execute("UPDATE domains SET status = 'in_review' WHERE id = ?", (domain_id,))
    await db.commit()
    with pytest.raises(ConflictError):
        await compile_domain(
            db,
            contributor_id=contributor_id,
            code="AC",
            llm=FakeLLM(default="x"),
        )


@pytest.mark.asyncio
async def test_compile_domain_blocks_skipped_answer(db):
    _, contributor_id, _ = await _seed_domain(db, answer_state="complete")
    await db.execute(
        "UPDATE answers SET skipped = 1, value = NULL, "
        "followups_state = 'complete' WHERE contributor_id = ?",
        (contributor_id,),
    )
    await db.commit()
    with pytest.raises(ConflictError) as exc:
        await compile_domain(
            db,
            contributor_id=contributor_id,
            code="AC",
            llm=FakeLLM(default="x"),
        )
    assert exc.value.code == "question_skipped"


@pytest.mark.asyncio
async def test_compile_domain_blocks_pending_followups(db):
    _, contributor_id, _ = await _seed_domain(db, answer_state="pending")
    with pytest.raises(ConflictError) as exc:
        await compile_domain(
            db,
            contributor_id=contributor_id,
            code="AC",
            llm=FakeLLM(default="x"),
        )
    assert exc.value.code == "followups_pending"


@pytest.mark.asyncio
async def test_compile_domain_surfaces_llm_failure(db):
    _, contributor_id, _ = await _seed_domain(db)
    with pytest.raises(Exception) as exc:
        await compile_domain(
            db,
            contributor_id=contributor_id,
            code="AC",
            llm=FakeLLM(fail=True),
        )
    assert "compilation failed" in str(exc.value).lower() or "retry" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_submit_domain_requires_compile(db):
    _, contributor_id, _ = await _seed_domain(db)
    with pytest.raises(ConflictError) as exc:
        await submit_domain(db, contributor_id=contributor_id, code="AC")
    assert exc.value.code == "domain_not_compiled"


@pytest.mark.asyncio
async def test_submit_domain_notifies_reviewer(db):
    await db.execute(
        _INSERT_USER,
        ("c@test.com", "x", '["contributor"]', "active", "s", 1),
    )
    row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",))
    contributor_id = row["id"]
    await db.execute(
        _INSERT_USER,
        ("r@test.com", "x", '["reviewer"]', "active", "s", 1),
    )
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("r@test.com",)))["id"]
    domain_id, _, _ = await _seed_domain(db, contributor_id=contributor_id, reviewer_id=reviewer_id)
    await db.execute(
        "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) VALUES (?, ?, ?)",
        (domain_id, "Compiled.", "2026-01-01T00:00:00"),
    )
    await db.commit()

    result = await submit_domain(db, contributor_id=contributor_id, code="AC")
    assert result["status"] == "in_review"

    notifications = await db.fetchall(
        "SELECT * FROM notifications WHERE user_id = ?",
        (reviewer_id,),
    )
    assert any(n["type"] == "domain_submitted" for n in notifications)
