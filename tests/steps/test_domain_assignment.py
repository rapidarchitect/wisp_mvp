"""pytest-bdd step definitions for domain assignment."""

import json
import sqlite3
from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/domain-assignment.feature", "ASSN-01 Admin assigns contributor and reviewer"
)
def test_assn01_admin_assigns_contributor_and_reviewer():
    pass


@scenario(
    "../../features/domain-assignment.feature", "ASSN-02 One contributor, one reviewer at a time"
)
def test_assn02_one_contributor_one_reviewer_at_a_time():
    pass


@scenario("../../features/domain-assignment.feature", "ASSN-03 Reassignment preserves work")
def test_assn03_reassignment_preserves_work():
    pass


@scenario(
    "../../features/domain-assignment.feature", "ASSN-04 Contributors see only assigned domains"
)
def test_assn04_contributors_see_only_assigned_domains():
    pass


@scenario("../../features/domain-assignment.feature", "ASSN-05 Unassigned domains flagged to admin")
def test_assn05_unassigned_domains_flagged_to_admin():
    pass


_DOMAIN_NAMES = {
    "AC": "Access Control",
    "PE": "Personnel",
}


def _tenant_db_path(data_dir: Path, slug: str) -> Path:
    return data_dir / "tenants" / f"{slug}.db"


@given(parsers.parse('domain "{code}" is ready for assignment'))
def given_domain_ready_for_assignment(data_dir, provisioned_tenant, code):
    """Ensure the domain exists in the current version and is marked ready."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE domains SET status = ? WHERE code = ?",
            ("ready", code),
        )
        conn.commit()
    finally:
        conn.close()


@when(
    parsers.parse(
        'the admin assigns domain "{code}" to "{contributor_email}" as contributor '
        'and "{reviewer_email}" as reviewer'
    )
)
def when_admin_assigns_domain(client, context, code, contributor_email, reviewer_email):
    """POST /domains/{code}/assign as the currently signed-in admin."""
    context["response"] = client.post(
        f"/domains/{code}/assign",
        json={"contributor_email": contributor_email, "reviewer_email": reviewer_email},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert context["response"].status_code == 200, context["response"].text


@then(
    parsers.parse(
        'domain "{code}" is assigned to "{contributor_email}" as contributor '
        'and "{reviewer_email}" as reviewer'
    )
)
def then_domain_assigned_to(
    data_dir, provisioned_tenant, context, code, contributor_email, reviewer_email
):
    """Assert the domain_assignments row matches the expected users."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        contributor_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (contributor_email,)
        ).fetchone()[0]
        reviewer_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (reviewer_email,)
        ).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]

        row = conn.execute(
            "SELECT contributor_id, reviewer_id FROM domain_assignments WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
        assert row is not None, f"No assignment found for domain {code}"
        assert row[0] == contributor_id
        assert row[1] == reviewer_id

        status = conn.execute("SELECT status FROM domains WHERE id = ?", (domain_id,)).fetchone()[0]
        assert status == "assigned"
    finally:
        conn.close()


@then(parsers.parse('"{email}" is notified of domain "{code}" assignment as {role}'))
def then_notified_assignment(data_dir, provisioned_tenant, email, code, role):
    """Assert a domain_assigned notification exists for the user."""
    _assert_notification(data_dir, provisioned_tenant, email, code, role, "domain_assigned")


@then(parsers.parse('"{email}" is notified of domain "{code}" unassignment as {role}'))
def then_notified_unassignment(data_dir, provisioned_tenant, email, code, role):
    """Assert a domain_unassigned notification exists for the user."""
    _assert_notification(data_dir, provisioned_tenant, email, code, role, "domain_unassigned")


def _assert_notification(data_dir, provisioned_tenant, email, code, role, kind):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_name = _DOMAIN_NAMES.get(code, code)
        row = conn.execute(
            """
            SELECT payload FROM notifications
            WHERE user_id = ? AND type = ? ORDER BY id DESC LIMIT 1
            """,
            (user_id, kind),
        ).fetchone()
        assert row is not None, f"No {kind} notification for {email}"
        payload = json.loads(row[0])
        assert payload.get("role") == role
        assert payload.get("domain_name") == domain_name
    finally:
        conn.close()


@when("they request their assigned domains")
def when_request_assigned_domains(client, context):
    """GET /domains/assigned for the currently signed-in user."""
    context["response"] = client.get(
        "/domains/assigned",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert context["response"].status_code == 200, context["response"].text


@then(parsers.parse('they see domain "{code}" with role "{role}"'))
def then_see_domain_with_role(context, code, role):
    """Assert the response contains the expected domain and role."""
    items = context["response"].json()
    matches = [item for item in items if item["code"] == code and item["role"] == role]
    assert len(matches) == 1, f"Expected exactly one match for {code}/{role}, got {matches}"


@then(parsers.parse('they do not see domain "{code}"'))
def then_do_not_see_domain(context, code):
    """Assert the response does not contain the domain."""
    items = context["response"].json()
    assert not any(item["code"] == code for item in items), f"Unexpectedly found domain {code}"


@when("the admin requests unassigned domains")
def when_admin_requests_unassigned_domains(client, context):
    """GET /domains/unassigned for the currently signed-in admin."""
    context["response"] = client.get(
        "/domains/unassigned",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert context["response"].status_code == 200, context["response"].text


@then(parsers.parse('domain "{code}" is flagged as missing "{roles}"'))
def then_domain_flagged_missing(context, code, roles):
    """Assert the unassigned-domain response flags the expected missing roles."""
    expected = [r.strip() for r in roles.split(",")]
    items = context["response"].json()
    matches = [item for item in items if item["code"] == code]
    assert len(matches) == 1, f"Expected exactly one flagged entry for {code}, got {matches}"
    assert matches[0]["missing_roles"] == expected


@then(parsers.parse('domain "{code}" is not flagged'))
def then_domain_not_flagged(context, code):
    """Assert the unassigned-domain response does not contain the domain."""
    items = context["response"].json()
    assert not any(item["code"] == code for item in items), (
        f"Unexpectedly found flagged domain {code}"
    )
