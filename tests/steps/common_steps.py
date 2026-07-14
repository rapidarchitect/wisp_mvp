"""Cross-feature Gherkin step definitions shared by BDD scenarios."""

import json
import sqlite3
from pathlib import Path

from pytest_bdd import given, parsers, then, when

from app.services.auth import hash_password
from app.services.provisioning import _DOMAINS
from app.services.totp import generate_totp_secret
from tests.steps.helpers import _tenant_db_path


def _roles_list(roles_str: str) -> list[str]:
    return [r.strip() for r in roles_str.split(",")]


def _find_user_id(data_dir: Path, slug: str, email: str) -> int:
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


def _domain_name(code: str) -> str:
    return dict(_DOMAINS).get(code, code)


@given(parsers.parse('a fully answered domain "{code}" for "{email}"'))
def given_fully_answered_domain(client, context, data_dir, provisioned_tenant, code, email):
    """Seed one answered question and set the domain to assigned.

    Preserves an existing domain assignment if one exists; otherwise assigns
    the named user as both contributor and reviewer.
    """
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        existing = conn.execute(
            "SELECT 1 FROM domain_assignments WHERE domain_id = ?", (domain_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                VALUES (?, ?, ?)
                """,
                (domain_id, user_id, user_id),
            )
        conn.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, "Fully answered question", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state)
            VALUES (?, ?, ?, ?, ?)
            """,
            (question_id, user_id, "yes", 0, "complete"),
        )
        conn.execute("UPDATE domains SET status = 'assigned' WHERE id = ?", (domain_id,))
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('a compiled domain "{code}" for "{email}"'))
def given_compiled_domain(client, context, data_dir, provisioned_tenant, code, email):
    """Seed one answered question and a compiled answer for submission.

    Preserves an existing domain assignment if one exists; otherwise assigns
    the named user as both contributor and reviewer.
    """
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        existing = conn.execute(
            "SELECT 1 FROM domain_assignments WHERE domain_id = ?", (domain_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                VALUES (?, ?, ?)
                """,
                (domain_id, user_id, user_id),
            )
        conn.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, "Compiled question", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state)
            VALUES (?, ?, ?, ?, ?)
            """,
            (question_id, user_id, "yes", 0, "complete"),
        )
        conn.execute(
            """
            INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at)
            VALUES (?, ?, ?)
            """,
            (domain_id, "Compiled narrative.", "2026-01-01T00:00:00"),
        )
        conn.execute("UPDATE domains SET status = 'assigned' WHERE id = ?", (domain_id,))
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('"{email}" compiles domain "{code}"'))
@when(parsers.parse('"{email}" compiles domain "{code}"'))
def when_user_compiles_domain(client, context, email, code):
    """POST to compile endpoint using the contributor's session token."""
    response = client.post(
        f"/domains/{code}/compile",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["compile_response"] = response.json()


@given(parsers.parse('"{email}" submits domain "{code}"'))
@when(parsers.parse('"{email}" submits domain "{code}"'))
def when_user_submits_domain(client, context, email, code):
    """POST to submit endpoint using the contributor's session token."""
    response = client.post(
        f"/domains/{code}/submit",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["submit_response"] = response.json()


@then("the compiled answer narrative is non-empty")
def then_compiled_narrative_non_empty(context):
    assert context["compile_response"]["narrative_text"]


@then(parsers.parse('a "{event_type}" audit event exists for domain "{code}"'))
def then_audit_event_for_domain(client, context, data_dir, provisioned_tenant, event_type, code):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = ? AND subject = ?",
            (event_type, f"domain:{code}"),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


@then(parsers.parse('the domain "{code}" status is "{status}"'))
def then_domain_status(client, context, data_dir, provisioned_tenant, code, status):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT status FROM domains WHERE code = ?", (code,))
        assert cur.fetchone()[0] == status
    finally:
        conn.close()


@then(parsers.parse('the contributor receives a "{kind}" notification'))
def then_contributor_notification(data_dir, provisioned_tenant, kind):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE type = ?",
            (kind,),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


@then(parsers.parse('the reviewer receives a "{kind}" notification'))
def then_reviewer_notification(data_dir, provisioned_tenant, kind):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE type = ?",
            (kind,),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


@given(
    parsers.re(
        r'^an enrolled user "(?P<email>[^"]+)" with password "(?P<password>[^"]+)" '
        r'and roles "(?P<roles>[^"]+)"$'
    )
)
def given_enrolled_user_with_roles(data_dir, provisioned_tenant, email, password, roles, context):
    """Create a user with the given roles and TOTP enrolled for possible login."""
    secret = generate_totp_secret()
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO users
                (email, password_hash, roles, status, totp_secret, totp_enrolled, failed_attempts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                hash_password(password),
                json.dumps(_roles_list(roles)),
                "active",
                secret,
                1,
                0,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    context.setdefault("users", {})[email] = {
        "email": email,
        "password": password,
        "totp_secret": secret,
    }


@given(
    parsers.parse(
        'domain "{code}" is assigned to "{contributor_email}" as contributor '
        'and "{reviewer_email}" as reviewer'
    )
)
def given_domain_assigned(
    data_dir, provisioned_tenant, code, contributor_email, reviewer_email, context
):
    """Seed a version, domain, and assignment for testing."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        contributor_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (contributor_email,)
        ).fetchone()[0]
        reviewer_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (reviewer_email,)
        ).fetchone()[0]
        version = conn.execute("SELECT id FROM wisp_versions WHERE number = 1").fetchone()
        if version is None:
            conn.execute(
                "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
                (1, 1, "in_progress"),
            )
            version_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            version_id = version[0]

        domain = conn.execute("SELECT id, status FROM domains WHERE code = ?", (code,)).fetchone()
        if domain is None:
            conn.execute(
                "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
                (code, _domain_name(code), version_id, "assigned"),
            )
            domain_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            domain_id = domain[0]
        conn.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            ON CONFLICT(domain_id) DO UPDATE SET
                contributor_id = excluded.contributor_id,
                reviewer_id = excluded.reviewer_id
            """,
            (domain_id, contributor_id, reviewer_id),
        )
        conn.commit()
        context["assigned_domain_id"] = domain_id
    finally:
        conn.close()


@given(parsers.parse('"{email}" has answered a question in domain "{code}"'))
def given_user_answered_question(data_dir, provisioned_tenant, email, code, context):
    """Seed a question and answer for the user in the given domain."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        conn.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (domain_id, "Do you lock doors?", "yes_no", "seeded", 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped) VALUES (?, ?, ?, ?)",
            (question_id, user_id, "yes", 0),
        )
        conn.commit()
    finally:
        conn.close()


@then(parsers.parse('the answer in domain "{code}" still exists'))
@then(parsers.parse('the answer in domain "{code}" is preserved'))
def then_answer_preserved(data_dir, context, code):
    """Verify answers still exist for the domain."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN domains d ON d.id = q.domain_id
            WHERE d.code = ?
            """,
            (code,),
        )
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
