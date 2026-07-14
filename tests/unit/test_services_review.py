"""Unit tests for the review workflow service."""

from __future__ import annotations

import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import AuthorizationError, ConflictError
from app.services.review import approve_domain, defer_domain, revise_and_approve


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


async def _seed_in_review_domain(
    db,
    *,
    contributor_id=None,
    reviewer_id=None,
    answer_state="complete",
    narrative="Compiled narrative.",
):
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
    await db.execute(_INSERT_DOMAIN, ("AC", "Access Control", version_id, "in_review"))
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
    await db.execute(
        "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) VALUES (?, ?, ?)",
        (domain_id, narrative, "2026-01-01T00:00:00"),
    )
    await db.commit()
    return domain_id, contributor_id, reviewer_id, version_id


@pytest.mark.asyncio
async def test_approve_domain_requires_in_review(db):
    await _seed_in_review_domain(db)
    contributor_id = (await db.fetchone("SELECT id FROM users"))["id"]
    await db.execute("UPDATE domains SET status = 'assigned' WHERE code = ?", ("AC",))
    await db.commit()
    with pytest.raises(ConflictError):
        await approve_domain(db, reviewer_id=contributor_id, code="AC")


@pytest.mark.asyncio
async def test_approve_domain_blocks_wrong_reviewer(db):
    await _seed_in_review_domain(db)
    await db.execute(
        _INSERT_USER,
        ("other@test.com", "x", '["reviewer"]', "active", "s", 1),
    )
    row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("other@test.com",))
    other_id = row["id"]
    await db.commit()
    with pytest.raises(AuthorizationError):
        await approve_domain(db, reviewer_id=other_id, code="AC")


@pytest.mark.asyncio
async def test_approve_domain_notifies_contributor(db):
    await _seed_in_review_domain(db)
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]

    result = await approve_domain(db, reviewer_id=reviewer_id, code="AC")
    assert result["status"] == "approved"

    notifications = await db.fetchall(
        "SELECT * FROM notifications WHERE user_id = ?",
        (reviewer_id,),
    )
    assert any(n["type"] == "domain_approved" for n in notifications)


@pytest.mark.asyncio
async def test_revise_and_approve_updates_narrative(db):
    await _seed_in_review_domain(db, narrative="Old narrative.")
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]

    result = await revise_and_approve(
        db,
        reviewer_id=reviewer_id,
        code="AC",
        revision_prompt="Add badge detail",
        llm=FakeLLM(default="Revised narrative with badges."),
    )
    assert result["status"] == "approved"

    compiled = await db.fetchone("SELECT * FROM compiled_answers")
    assert "badges" in compiled["narrative_text"].lower()
    assert compiled["revised_by_reviewer_id"] == reviewer_id


@pytest.mark.asyncio
async def test_revise_and_approve_surfaces_llm_failure(db):
    await _seed_in_review_domain(db, narrative="Old narrative.")
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]

    with pytest.raises(Exception) as exc:
        await revise_and_approve(
            db,
            reviewer_id=reviewer_id,
            code="AC",
            revision_prompt="Make it better",
            llm=FakeLLM(fail=True),
        )
    assert "revision failed" in str(exc.value).lower()

    compiled = await db.fetchone("SELECT * FROM compiled_answers")
    assert compiled["narrative_text"] == "Old narrative."
    assert compiled["revised_by_reviewer_id"] is None


@pytest.mark.asyncio
async def test_defer_domain_returns_to_in_progress(db):
    await _seed_in_review_domain(db)
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]

    result = await defer_domain(db, reviewer_id=reviewer_id, code="AC")
    assert result["status"] == "in_progress"

    notifications = await db.fetchall(
        "SELECT * FROM notifications WHERE user_id = ?",
        (reviewer_id,),
    )
    assert any(n["type"] == "domain_deferred" for n in notifications)


@pytest.mark.asyncio
async def test_self_review_warning(db):
    await _seed_in_review_domain(db)
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]

    result = await approve_domain(db, reviewer_id=reviewer_id, code="AC")
    assert result["self_review"] is True


@pytest.mark.asyncio
async def test_wisp_complete_when_all_14_approved(db):
    _, contributor_id, _, version_id = await _seed_in_review_domain(db, reviewer_id=None)
    reviewer_id = contributor_id

    codes = [
        "AC",
        "PE",
        "RA",
        "CA",
        "SC",
        "SI",
        "AT",
        "AU",
        "CM",
        "IA",
        "IR",
        "MA",
        "MP",
        "PS",
    ]
    for code in codes:
        if code == "AC":
            continue
        await db.execute(
            _INSERT_DOMAIN,
            (code, f"Domain {code}", version_id, "in_review"),
        )
        domain_id = (await db.fetchone("SELECT id FROM domains WHERE code = ?", (code,)))["id"]
        await db.execute(
            _INSERT_ASSIGNMENT,
            (domain_id, contributor_id, reviewer_id),
        )
        await db.execute(
            "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) "
            "VALUES (?, ?, ?)",
            (domain_id, f"Narrative {code}.", "2026-01-01T00:00:00"),
        )

    await db.execute(
        _INSERT_USER,
        ("admin@test.com", "x", '["admin"]', "active", "s", 1),
    )
    row = await db.fetchone("SELECT id FROM users WHERE email = ?", ("admin@test.com",))
    admin_id = row["id"]
    await db.commit()

    for code in codes:
        result = await approve_domain(db, reviewer_id=reviewer_id, code=code)
        if code == "PS":
            assert result["wisp_complete"] is True

    version = await db.fetchone("SELECT * FROM wisp_versions WHERE id = ?", (version_id,))
    assert version["status"] == "complete"

    notifications = await db.fetchall(
        "SELECT * FROM notifications WHERE user_id = ?",
        (admin_id,),
    )
    assert any(n["type"] == "wisp_complete" for n in notifications)
