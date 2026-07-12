"""pytest-bdd step definitions for the authentication feature."""

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/authentication.feature",
    "Wrong password rejected (AUTH-03)",
)
def test_wrong_password_rejected_auth03():
    pass


@scenario(
    "../../features/authentication.feature",
    "Lock after 5 failed attempts (AUTH-05)",
)
def test_lock_after_5_failed_attempts_auth05():
    pass


@scenario(
    "../../features/authentication.feature",
    "Expired session preserves saved work (AUTH-06)",
)
def test_expired_session_preserves_saved_work_auth06():
    pass


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


@given(
    parsers.parse("the user has a session issued {hours:d} hours ago"),
    target_fixture="session_token",
)
def given_session_issued_hours_ago(provisioned_tenant, data_dir, enrolled_user, hours):
    """Create a session in the past using freezegun."""
    from freezegun import freeze_time

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    issued_at = now - timedelta(hours=hours)
    expires_at = issued_at + timedelta(hours=8)
    with freeze_time(issued_at):
        path = _tenant_db_path(data_dir, provisioned_tenant)
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO sessions (user_id, token, issued_at, expires_at) VALUES (?, ?, ?, ?)",
            (enrolled_user["id"], token, issued_at.isoformat(), expires_at.isoformat()),
        )
        conn.commit()
        conn.close()
    return token


@given(parsers.parse('the user saved an answer "{text}"'))
def given_saved_answer(provisioned_tenant, data_dir, enrolled_user, text):
    """Seed a minimal domain, question, and answer so saved work can be verified."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
            (1, 1, "in_progress"),
        )
        version_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
            ("AC", "Access Control", version_id, "in_progress"),
        )
        domain_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO questions (domain_id, text, position) VALUES (?, ?, ?)",
            (domain_id, "Is access controlled?", 1),
        )
        question_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO answers (question_id, contributor_id, value, followups_state)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, enrolled_user["id"], text, "complete"),
        )
        conn.commit()
    finally:
        conn.close()


@when(parsers.parse('the user logs in with password "{password}"'))
def when_user_logs_in(client, context, enrolled_user, password):
    """POST /auth/login with the user's email and the supplied password."""
    context["response"] = client.post(
        "/auth/login",
        json={"email": enrolled_user["email"], "password": password},
    )


@when(parsers.parse('the user logs in with password "{password}" {count:d} times'))
def when_user_logs_in_multiple_times(client, context, enrolled_user, password, count):
    """Attempt login multiple times and keep the last response."""
    for _ in range(count):
        context["response"] = client.post(
            "/auth/login",
            json={"email": enrolled_user["email"], "password": password},
        )


@when(parsers.parse('the user logs in with password "{password}" again'))
def when_user_logs_in_again(client, context, enrolled_user, password):
    """One more login attempt after lockout."""
    context["response"] = client.post(
        "/auth/login",
        json={"email": enrolled_user["email"], "password": password},
    )


@when("the user uses the session after 8 hours and 1 minute")
def when_user_uses_expired_session(client, context, session_token):
    """Advance time past expiry and call a protected endpoint."""
    from freezegun import freeze_time

    future = datetime.now(UTC) + timedelta(hours=8, minutes=1)
    with freeze_time(future):
        context["response"] = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {session_token}"},
        )


@then(parsers.parse('the login is rejected with "{code}"'))
def then_login_rejected(context, code):
    """Assert the login response status and error code."""
    response = context["response"]
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code


@then("no session is created")
def then_no_session_created(provisioned_tenant, data_dir, enrolled_user):
    """Verify the user has no sessions in the tenant database."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) AS count FROM sessions WHERE user_id = ?",
            (enrolled_user["id"],),
        )
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()


@then("the account is locked for 15 minutes")
def then_account_locked(provisioned_tenant, data_dir, enrolled_user):
    """Verify the user's locked_until timestamp is roughly 15 minutes ahead."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT locked_until FROM users WHERE id = ?",
            (enrolled_user["id"],),
        )
        locked_until = cur.fetchone()[0]
        assert locked_until is not None
        locked_until = datetime.fromisoformat(locked_until)
        now = datetime.now(UTC)
        assert timedelta(minutes=14) < (locked_until - now) < timedelta(minutes=16)
    finally:
        conn.close()


@then("the session is rejected as expired")
def then_session_rejected_expired(context):
    """Assert the protected endpoint rejects the expired session."""
    response = context["response"]
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


@then(parsers.parse('the answer "{text}" still exists'))
def then_answer_still_exists(provisioned_tenant, data_dir, text):
    """Verify the saved answer row is still present."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT value FROM answers WHERE value = ?",
            (text,),
        )
        assert cur.fetchone() is not None
    finally:
        conn.close()
