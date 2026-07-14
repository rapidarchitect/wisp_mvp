"""Step definitions for review-workflow.feature."""

from __future__ import annotations

import sqlite3

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from app.ai.fakes import FakeLLM
from tests.steps.helpers import _tenant_db_path


@pytest.fixture(autouse=True)
def _fake_revision_llm(monkeypatch):
    """Return deterministic revisions for review scenarios."""
    monkeypatch.setattr(
        "app.crews.revision_crew.create_llm",
        lambda _provider=None: FakeLLM(
            default="Revised narrative that includes access logs and badges."
        ),
    )


@scenario(
    "../../features/review-workflow.feature",
    "REVW-01 Reviewer approves compiled answer",
)
def test_revw01_reviewer_approves():
    pass


@scenario(
    "../../features/review-workflow.feature",
    "REVW-02 Edit produces AI revision and direct approval",
)
def test_revw02_reviewer_revises():
    pass


@scenario(
    "../../features/review-workflow.feature",
    "REVW-03 Reviewer defers decision",
)
def test_revw03_reviewer_defers():
    pass


@scenario(
    "../../features/review-workflow.feature",
    "REVW-04 Self-review shows warning",
)
def test_revw04_self_review_warning():
    pass


@scenario(
    "../../features/review-workflow.feature",
    "REVW-05 All approved completes the WISP",
)
def test_revw05_all_approved_completes_wisp():
    pass


@given(parsers.parse('a submitted domain "{code}"'))
def given_submitted_domain(data_dir, provisioned_tenant, code, context):
    """Ensure the domain is in_review with a compiled answer."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        conn.execute("UPDATE domains SET status = 'in_review' WHERE id = ?", (domain_id,))
        existing = conn.execute(
            "SELECT id FROM compiled_answers WHERE domain_id = ?", (domain_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) "
                "VALUES (?, ?, ?)",
                (domain_id, "Submitted narrative.", "2026-01-01T00:00:00"),
            )
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('all 14 domains are submitted for "{email}"'))
def given_all_14_domains_submitted(data_dir, provisioned_tenant, email, context):
    """Set all 14 domains in_review with compiled answers for the contributor."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        version_id = conn.execute("SELECT id FROM wisp_versions").fetchone()[0]
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
        reviewer_id = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("reviewer@palmetto.app.wisp.llc",),
        ).fetchone()[0]
        for idx, code in enumerate(codes):
            domain_id = conn.execute(
                "SELECT id FROM domains WHERE code = ? AND wisp_version_id = ?",
                (code, version_id),
            ).fetchone()[0]
            conn.execute("DELETE FROM domain_assignments WHERE domain_id = ?", (domain_id,))
            conn.execute(
                "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) "
                "VALUES (?, ?, ?)",
                (domain_id, user_id, reviewer_id),
            )
            # Approve all but the last domain so the final approval completes the WISP.
            status = "approved" if idx < len(codes) - 1 else "in_review"
            conn.execute("UPDATE domains SET status = ? WHERE id = ?", (status, domain_id))
            conn.execute(
                "DELETE FROM notifications WHERE EXISTS ("
                "SELECT 1 FROM users u WHERE u.id = notifications.user_id AND u.email = ?"
                ")",
                ("admin@palmetto.app.wisp.llc",),
            )
            existing = conn.execute(
                "SELECT id FROM compiled_answers WHERE domain_id = ?", (domain_id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) "
                    "VALUES (?, ?, ?)",
                    (domain_id, f"Narrative {code}.", "2026-01-01T00:00:00"),
                )
        conn.commit()
        context["last_domain_code"] = "PS"
    finally:
        conn.close()


@when(parsers.parse('the reviewer approves domain "{code}"'))
def when_reviewer_approves_domain(client, context, code):
    response = client.post(
        f"/domains/{code}/approve",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["approve_response"] = response.json()


@when(parsers.parse('the reviewer revises domain "{code}" with prompt "{prompt}"'))
def when_reviewer_revises_domain(client, context, code, prompt):
    response = client.post(
        f"/domains/{code}/revise",
        json={"revision_prompt": prompt},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["revise_response"] = response.json()


@when(parsers.parse('the reviewer defers domain "{code}"'))
def when_reviewer_defers_domain(client, context, code):
    response = client.post(
        f"/domains/{code}/defer",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["defer_response"] = response.json()


@when("the reviewer approves the last domain")
def when_reviewer_approves_last_domain(client, context):
    code = context["last_domain_code"]
    response = client.post(
        f"/domains/{code}/approve",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["approve_response"] = response.json()


@then(parsers.parse('the compiled answer narrative contains "{text}"'))
def then_compiled_narrative_contains(client, context, data_dir, provisioned_tenant, text):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        # The scenario does not pass the domain code, but AC is the only revised domain.
        narrative = conn.execute(
            "SELECT narrative_text FROM compiled_answers WHERE domain_id = "
            "(SELECT id FROM domains WHERE code = 'AC')"
        ).fetchone()[0]
        assert text.lower() in narrative.lower()
    finally:
        conn.close()


@then("the response includes a self-review warning")
def then_response_includes_self_review_warning(context):
    assert context["approve_response"]["self_review"] is True


@then(parsers.parse('the WISP version status is "{status}"'))
def then_wisp_version_status(client, context, data_dir, provisioned_tenant, status):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT status FROM wisp_versions")
        assert cur.fetchone()[0] == status
    finally:
        conn.close()


@then(parsers.parse('the admin receives a "{kind}" notification'))
def then_admin_notification(data_dir, provisioned_tenant, kind):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        admin_id = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("admin@palmetto.app.wisp.llc",),
        ).fetchone()[0]
        cur = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND type = ?",
            (admin_id, kind),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()
