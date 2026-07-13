"""pytest-bdd step definitions for domain seeding and questions."""

import asyncio
import sqlite3

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from app.ai.fakes import FakeLLM
from app.cli import seed_demo


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "14 domains seeded, 5-10 questions each (SEED-01)",
)
def test_14_domains_seeded_5_10_questions_seed01():
    pass


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "Demo company after deployment (SEED-02)",
)
def test_demo_company_after_deployment_seed02():
    pass


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "Research outage degrades gracefully (SEED-03)",
)
def test_research_outage_degrades_gracefully_seed03():
    pass


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "Admin adds custom question (SEED-04)",
)
def test_admin_adds_custom_question_seed04():
    pass


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "Admin disables seeded question (SEED-05)",
)
def test_admin_disables_seeded_question_seed05():
    pass


@scenario(
    "../../features/domain-seeding-and-questions.feature",
    "Regeneration only when unanswered (SEED-06)",
)
def test_regeneration_only_when_unanswered_seed06():
    pass


@pytest.fixture
def seed_all_domains_result(data_dir, provisioned_tenant, context):
    """Run seed_all_domains for the provisioned tenant (async work in fixture)."""
    from app.db.tenant import get_tenant_db
    from app.services.seeding import seed_all_domains

    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        version_row = conn.execute("SELECT id FROM wisp_versions WHERE number = 1").fetchone()
        version_id = version_row[0]
    finally:
        conn.close()

    llm = context.get(
        "llm",
        FakeLLM(
            default='{"questions": ['
            '{"text": "Q1?"}, '
            '{"text": "Q2?"}, '
            '{"text": "Q3?"}, '
            '{"text": "Q4?"}, '
            '{"text": "Q5?"}'
            "]}"
        ),
    )

    async def _run():
        tenant_db = await get_tenant_db(data_dir, provisioned_tenant)
        try:
            return await seed_all_domains(tenant_db, version_id=version_id, llm=llm)
        finally:
            await tenant_db.close()

    result = asyncio.run(_run())
    context["seed_result"] = result
    return result


@pytest.fixture
def seed_demo_result(data_dir, context):
    """Run the seed-demo CLI handler (async work in fixture)."""
    llm = context.get(
        "llm",
        FakeLLM(
            default='{"questions": ['
            '{"text": "Q1?"}, '
            '{"text": "Q2?"}, '
            '{"text": "Q3?"}, '
            '{"text": "Q4?"}, '
            '{"text": "Q5?"}'
            "]}"
        ),
    )
    result = asyncio.run(seed_demo(data_dir=str(data_dir), llm=llm))
    context["seed_demo_result"] = result
    return result


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


def _find_domain_id(data_dir, slug, code):
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


def _find_seeded_question_id(data_dir, slug, code):
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT q.id FROM questions q JOIN domains d ON d.id = q.domain_id "
            "WHERE d.code = ? AND q.origin = 'seeded' LIMIT 1",
            (code,),
        ).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


@when("the admin seeds all domains")
def when_admin_seeds_all_domains(seed_all_domains_result):
    """Domain seeding is handled by the seed_all_domains_result fixture."""


@then("14 domains exist")
def then_14_domains_exist(data_dir, provisioned_tenant):
    """Verify the tenant has 14 domains."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
        assert count == 14
    finally:
        conn.close()


@then("each domain has between 5 and 10 questions")
def then_each_domain_has_between_5_and_10_questions(data_dir, provisioned_tenant, context):
    """Verify every domain has 5-10 questions for the seeded tenant."""
    slug = "demo" if "seed_demo_result" in context else provisioned_tenant
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT d.id, COUNT(q.id)
            FROM domains d
            LEFT JOIN questions q ON q.domain_id = d.id
            GROUP BY d.id
            """
        ).fetchall()
        assert len(rows) == 14
        for _domain_id, count in rows:
            assert 5 <= count <= 10
    finally:
        conn.close()


@then("all questions are yes-no questions")
def then_all_questions_are_yes_no(data_dir, provisioned_tenant):
    """Verify every seeded question has answer_type yes_no."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT answer_type FROM questions").fetchall()
        assert len(rows) > 0
        for (answer_type,) in rows:
            assert answer_type == "yes_no"
    finally:
        conn.close()


@when("the operator runs the seed-demo command")
def when_operator_runs_seed_demo(seed_demo_result):
    """Seed-demo execution is handled by the seed_demo_result fixture."""


@then("the demo tenant has 14 domains")
def then_demo_tenant_has_14_domains(data_dir):
    """Verify the demo tenant database contains 14 domains."""
    path = _tenant_db_path(data_dir, "demo")
    conn = sqlite3.connect(path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
        assert count == 14
    finally:
        conn.close()


@then('a demo tenant "demo" is provisioned')
def then_demo_tenant_provisioned(data_dir):
    """Verify the demo tenant record and database file exist."""
    control_db = data_dir / "control.db"
    conn = sqlite3.connect(control_db)
    try:
        row = conn.execute("SELECT status FROM tenants WHERE slug = ?", ("demo",)).fetchone()
        assert row is not None
        assert row[0] == "active"
    finally:
        conn.close()
    assert (_tenant_db_path(data_dir, "demo")).exists()


@given("the LLM is set to fail")
def given_llm_is_set_to_fail(context):
    """Configure a FakeLLM that raises on every call."""
    context["llm"] = FakeLLM(fail=True)


@then("seeding is marked as pending for at least one domain")
def then_seeding_marked_pending(data_dir, provisioned_tenant):
    """Verify at least one domain has status pending_questions after outage."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT status FROM domains").fetchall()
        statuses = {r[0] for r in rows}
        assert "pending_questions" in statuses
    finally:
        conn.close()


@then("no exception is raised")
def then_no_exception_is_raised(context):
    """The previous step already completed; this is a readability step."""
    assert "seed_result" in context


@given(parsers.parse('domain "{code}" is ready'))
def given_domain_is_ready(data_dir, provisioned_tenant, code):
    """Ensure the named domain is ready with at least 5 enabled questions.

    This step both sets up state (inserting yes-no questions when missing) and
    verifies the final condition, so it can be used as a self-contained Given.
    """
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id, status FROM domains WHERE code = ?", (code,)).fetchone()
        assert row is not None, f"Domain {code} not found"
        domain_id, status = row

        if status != "ready":
            conn.execute(
                "UPDATE domains SET status = 'ready' WHERE id = ?",
                (domain_id,),
            )

        count = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
            (domain_id,),
        ).fetchone()[0]
        if count < 5:
            for i in range(5 - count):
                conn.execute(
                    """
                    INSERT INTO questions
                        (domain_id, text, answer_type, origin, enabled, position)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (domain_id, f"Ready question {i + 1}?", "yes_no", "seeded", 1, i),
                )

        conn.commit()

        row = conn.execute("SELECT status FROM domains WHERE id = ?", (domain_id,)).fetchone()
        assert row[0] == "ready", f"Domain {code} is {row[0]}, expected ready"
        count = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
            (domain_id,),
        ).fetchone()[0]
        assert count >= 5, f"Domain {code} has only {count} enabled questions"
    finally:
        conn.close()


@given(parsers.parse('the admin has added a custom question to domain "{code}"'))
def given_admin_added_custom_question(client, data_dir, provisioned_tenant, context, code):
    """Seed a custom question through the API so the domain has >5 enabled."""
    domain_id = _find_domain_id(data_dir, provisioned_tenant, code)
    response = client.post(
        "/questions",
        json={"domain_id": domain_id, "text": "Extra admin question?"},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200


@when(parsers.parse('the admin adds a custom question "{text}" to domain "{code}"'))
def when_admin_adds_question(client, data_dir, provisioned_tenant, context, text, code):
    """POST a new custom question."""
    domain_id = _find_domain_id(data_dir, provisioned_tenant, code)
    response = client.post(
        "/questions",
        json={"domain_id": domain_id, "text": text},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["last_question_id"] = response.json()["question_id"]


@then(parsers.parse('domain "{code}" has {count:d} enabled questions'))
def then_domain_has_enabled_questions(data_dir, provisioned_tenant, code, count):
    """Count enabled questions for the domain."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        n = conn.execute(
            """
            SELECT COUNT(*) FROM questions q
            JOIN domains d ON d.id = q.domain_id
            WHERE d.code = ? AND q.enabled = 1
            """,
            (code,),
        ).fetchone()[0]
        assert n == count
    finally:
        conn.close()


@then(parsers.parse('the new question has origin "{origin}"'))
def then_new_question_has_origin(data_dir, provisioned_tenant, context, origin):
    """Assert the last created question's origin."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT origin FROM questions WHERE id = ?",
            (context["last_question_id"],),
        ).fetchone()
        assert row is not None
        assert row[0] == origin
    finally:
        conn.close()


@when(parsers.parse('the admin disables a seeded question in domain "{code}"'))
def when_admin_disables_seeded_question(client, data_dir, provisioned_tenant, context, code):
    """Disable the first seeded question in the domain."""
    question_id = _find_seeded_question_id(data_dir, provisioned_tenant, code)
    response = client.post(
        f"/questions/{question_id}/disable",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["disabled_question_id"] = question_id


@then("the disabled question is hidden")
def then_disabled_question_is_hidden(data_dir, provisioned_tenant, context):
    """Assert the disabled question is no longer enabled."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM questions WHERE id = ?",
            (context["disabled_question_id"],),
        ).fetchone()[0]
        assert enabled == 0
    finally:
        conn.close()


@when(parsers.parse('the admin regenerates questions for domain "{code}"'))
def when_admin_regenerates_questions(client, data_dir, provisioned_tenant, context, code):
    """POST to regenerate seeded questions for the domain."""
    domain_id = _find_domain_id(data_dir, provisioned_tenant, code)
    # Reset the baseline each time so multiple regenerations compare against the right set.
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        context["pre_regeneration_ids"] = {
            r[0]
            for r in conn.execute(
                "SELECT id FROM questions WHERE domain_id = ?", (domain_id,)
            ).fetchall()
        }
    finally:
        conn.close()
    response = client.post(
        f"/domains/{domain_id}/regenerate-questions",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    context["last_regenerate_response"] = response


@then(parsers.parse('domain "{code}" has fresh seeded questions'))
def then_domain_has_fresh_seeded_questions(data_dir, provisioned_tenant, code, context):
    """Assert questions were replaced and all are seeded."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT q.id, q.origin FROM questions q
            JOIN domains d ON d.id = q.domain_id
            WHERE d.code = ?
            """,
            (code,),
        ).fetchall()
        assert len(rows) >= 5
        current_ids = {r[0] for r in rows}
        assert not current_ids & context["pre_regeneration_ids"]
        assert all(r[1] == "seeded" for r in rows)
    finally:
        conn.close()


@when(parsers.parse('a contributor answers a question in domain "{code}"'))
def when_contributor_answers_question(data_dir, provisioned_tenant, code, context):
    """Insert an answer directly so the domain is no longer answer-free."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        question_id = conn.execute(
            "SELECT id FROM questions WHERE domain_id = ? LIMIT 1", (domain_id,)
        ).fetchone()[0]
        email = f"c@{provisioned_tenant}.app.wisp.llc"
        conn.execute(
            """
            INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, "hash", '["contributor"]', "active", 0, 0),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped) VALUES (?, ?, ?, ?)",
            (question_id, user_id, "yes", 0),
        )
        conn.commit()
    finally:
        conn.close()


@then(parsers.parse('the regeneration is rejected with "{code}"'))
def then_regeneration_rejected(context, code):
    """Assert the last regeneration attempt failed with the expected error code."""
    response = context["last_regenerate_response"]
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
