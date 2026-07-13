"""pytest-bdd step definitions for domain seeding and questions."""

import asyncio
import sqlite3

from pytest_bdd import given, scenario, then, when

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


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


@when("the admin seeds all domains")
def when_admin_seeds_all_domains(data_dir, provisioned_tenant, context):
    """Run domain seeding for the tenant's WISP version 1."""
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

    context["seed_result"] = asyncio.run(_run())


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
def when_operator_runs_seed_demo(data_dir, context):
    """Invoke the seed-demo CLI handler directly."""
    llm = FakeLLM(
        default='{"questions": ['
        '{"text": "Q1?"}, '
        '{"text": "Q2?"}, '
        '{"text": "Q3?"}, '
        '{"text": "Q4?"}, '
        '{"text": "Q5?"}'
        "]}"
    )
    context["seed_demo_result"] = asyncio.run(seed_demo(data_dir=str(data_dir), llm=llm))


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
