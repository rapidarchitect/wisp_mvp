"""pytest-bdd step definitions for user and role management."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pyotp
from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/user-and-role-management.feature",
    "Invite user with two roles (USER-01)",
)
def test_invite_user_with_two_roles_user01():
    pass


@scenario(
    "../../features/user-and-role-management.feature",
    "Invited user activates account (USER-02)",
)
def test_invited_user_activates_account_user02():
    pass


@scenario(
    "../../features/user-and-role-management.feature",
    "One user holds all three roles (USER-03)",
)
def test_one_user_holds_all_three_roles_user03():
    pass


@scenario(
    "../../features/user-and-role-management.feature",
    "Duplicate invitation rejected (USER-04)",
)
def test_duplicate_invitation_rejected_user04():
    pass


@scenario(
    "../../features/user-and-role-management.feature",
    "Expired invitation link refused (USER-05)",
)
def test_expired_invitation_link_refused_user05():
    pass


@scenario(
    "../../features/user-and-role-management.feature",
    "Deactivation flags domains, keeps answers (USER-06)",
)
def test_deactivation_flags_domains_keeps_answers_user06():
    pass


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


def _roles_list(roles_str: str) -> list[str]:
    return [r.strip() for r in roles_str.split(",")]


@given(parsers.parse('the admin invites "{email}" with roles "{roles}"'))
@when(parsers.parse('the admin invites "{email}" with roles "{roles}"'))
def admin_invites(client, context, email, roles):
    """POST /users/invite with the admin session."""
    context["response"] = client.post(
        "/users/invite",
        json={"email": email, "roles": roles},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    if context["response"].status_code == 200:
        context["invitation_token"] = context["response"].json()["token"]
        context["invited_email"] = email


@then(parsers.parse('an invitation exists for "{email}" with roles "{roles}"'))
def then_invitation_exists(data_dir, context, email, roles):
    """Verify the invitation row in the tenant DB."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            """
            SELECT roles, token, expires_at FROM invitations
            WHERE email = ? AND accepted_at IS NULL
            """,
            (email,),
        )
        row = cur.fetchone()
        assert row is not None
        assert json.loads(row[0]) == _roles_list(roles)
        context["invitation_token"] = row[1]
        context["invitation_expires_at"] = row[2]
    finally:
        conn.close()


@then("the invitation expires in 7 days")
def then_invitation_expires_in_7_days(context):
    """Verify the invitation expiry is 7 days from now."""
    expires_at = datetime.fromisoformat(context["invitation_expires_at"])
    now = datetime.now(UTC)
    delta = expires_at - now
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)


@when(
    parsers.parse('the invited user accepts with password "{password}" and TOTP secret "{secret}"')
)
def when_invited_user_accepts(client, context, password, secret):
    """POST /users/accept with the invitation token."""
    context["response"] = client.post(
        "/users/accept",
        json={
            "token": context["invitation_token"],
            "password": password,
            "totp_secret": secret,
        },
    )


@then(parsers.parse('a user exists for "{email}" with roles "{roles}"'))
def then_user_exists(data_dir, context, email, roles):
    """Verify the activated user row."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT roles, totp_enrolled FROM users WHERE email = ?",
            (email,),
        )
        row = cur.fetchone()
        assert row is not None
        assert json.loads(row[0]) == _roles_list(roles)
        assert row[1] == 1
    finally:
        conn.close()


@then(parsers.parse('the user can log in with password "{password}" and TOTP "{secret}"'))
def then_user_can_log_in(client, context, password, secret):
    """Verify the activated user can authenticate."""
    email = context["invited_email"]
    totp = pyotp.TOTP(secret)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "totp_code": totp.now()},
    )
    assert response.status_code == 200
    assert "token" in response.json()


@given(parsers.parse('an enrolled user "{email}" with password "{password}"'))
def given_enrolled_user_plain(data_dir, provisioned_tenant, email, password, context):
    """Create a user with no specific roles."""
    from app.services.auth import hash_password

    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, hash_password(password), json.dumps([]), "active", 0, 0),
        )
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('an enrolled user "{email}" with password "{password}" and roles "{roles}"'))
def given_enrolled_user_with_roles(data_dir, provisioned_tenant, email, password, roles, context):
    """Create a user with the given roles and TOTP enrolled for possible login."""
    from app.services.auth import hash_password
    from app.services.totp import generate_totp_secret

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
    context["target_user"] = {"email": email, "password": password, "totp_secret": secret}


@when(parsers.parse('the admin sets roles for "{email}" to "{roles}"'))
def when_admin_sets_roles(client, data_dir, tenant_slug, context, email, roles):
    """Find user by email and POST /users/{id}/roles."""
    user_id = _find_user_id(data_dir=data_dir, slug=tenant_slug, email=email)
    context["response"] = client.post(
        f"/users/{user_id}/roles",
        json={"roles": roles},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )


@then(parsers.parse('the user "{email}" has roles "{roles}"'))
def then_user_has_roles(data_dir, context, email, roles):
    """Verify the user's roles in the DB."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT roles FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        assert row is not None
        assert json.loads(row[0]) == _roles_list(roles)
    finally:
        conn.close()


@then(parsers.parse('the invitation is rejected with "{code}"'))
def then_invitation_rejected(context, code):
    """Assert the invite response status and error code."""
    response = context["response"]
    assert response.status_code in (409, 422)
    assert response.json()["error"]["code"] == code


@when("7 days pass")
def when_7_days_pass(context):
    """Advance freezegun by 7 days."""
    from freezegun import freeze_time

    freezer = freeze_time(lambda: datetime.now(UTC) + timedelta(days=7))
    freezer.start()
    context["freezer"] = freezer


@then(parsers.parse('the acceptance is rejected with "{code}"'))
def then_acceptance_rejected(context, code):
    """Assert the acceptance response status and error code, then stop freezer."""
    response = context["response"]
    if "freezer" in context:
        context["freezer"].stop()
    assert response.status_code in (409, 422)
    assert response.json()["error"]["code"] == code


@given(
    parsers.parse(
        'domain "{code}" is assigned to "{contributor_email}" as contributor '
        'and "{reviewer_email}" as reviewer'
    )
)
def given_domain_assigned(
    data_dir, provisioned_tenant, code, contributor_email, reviewer_email, context
):
    """Seed a version, domain, and assignment for deactivation testing."""
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

        domain = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()
        if domain is None:
            conn.execute(
                "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
                (code, "Access Control", version_id, "assigned"),
            )
            domain_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            domain_id = domain[0]
            conn.execute(
                "UPDATE domains SET status = ? WHERE id = ?",
                ("assigned", domain_id),
            )
        conn.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            """,
            (domain_id, contributor_id, reviewer_id),
        )
        conn.commit()
        context["deactivate_domain_id"] = domain_id
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


@when(parsers.parse('the admin deactivates "{email}"'))
def when_admin_deactivates(client, data_dir, tenant_slug, context, email):
    """Find user by email and POST /users/{id}/deactivate."""
    user_id = _find_user_id(data_dir=data_dir, slug=tenant_slug, email=email)
    context["response"] = client.post(
        f"/users/{user_id}/deactivate",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )


@then(parsers.parse('the user "{email}" is deactivated'))
def then_user_is_deactivated(data_dir, context, email):
    """Verify the user's status is deactivated."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT status FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "deactivated"
    finally:
        conn.close()


@then(parsers.parse('domain "{code}" is flagged as unassigned'))
def then_domain_flagged_unassigned(data_dir, context, code):
    """Verify the domain has no assignment and status pending."""
    path = _tenant_db_path(data_dir, context.get("tenant_slug", "palmetto"))
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT status FROM domains WHERE code = ?",
            (code,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "pending_questions"
        cur = conn.execute(
            "SELECT COUNT(*) FROM domain_assignments WHERE domain_id = ?",
            (context["deactivate_domain_id"],),
        )
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()


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


def _find_user_id(data_dir, slug, email):
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()
