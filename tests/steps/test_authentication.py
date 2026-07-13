"""pytest-bdd step definitions for the authentication feature."""

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

import pyotp
from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/authentication.feature",
    "First login requires TOTP enrollment (AUTH-01)",
)
def test_first_login_requires_totp_enrollment_auth01():
    pass


@scenario(
    "../../features/authentication.feature",
    "Login with password and TOTP (AUTH-02)",
)
def test_login_with_password_and_totp_auth02():
    pass


@scenario(
    "../../features/authentication.feature",
    "Wrong password rejected (AUTH-03)",
)
def test_wrong_password_rejected_auth03():
    pass


@scenario(
    "../../features/authentication.feature",
    "Wrong TOTP counts toward lockout (AUTH-04)",
)
def test_wrong_totp_counts_toward_lockout_auth04():
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


@scenario(
    "../../features/authentication.feature",
    "Password reset via 30-min link (AUTH-07)",
)
def test_password_reset_via_30_min_link_auth07():
    pass


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


@given("the user has enrolled TOTP")
def given_user_has_enrolled_totp(provisioned_tenant, data_dir, enrolled_user, context):
    """Generate a TOTP secret and mark the user as enrolled."""
    from app.services.totp import generate_totp_secret

    secret = generate_totp_secret()
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE users SET totp_secret = ?, totp_enrolled = 1 WHERE id = ?",
            (secret, enrolled_user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    context["totp_secret"] = secret


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


@when(parsers.parse('the user logs in with password "{password}" and current TOTP'))
def when_user_logs_in_with_current_totp(client, context, enrolled_user, password):
    """POST /auth/login with a freshly generated TOTP code."""
    secret = context["totp_secret"]
    code = pyotp.TOTP(secret).now()
    context["response"] = client.post(
        "/auth/login",
        json={
            "email": enrolled_user["email"],
            "password": password,
            "totp_code": code,
        },
    )


@when(parsers.parse('the user logs in with password "{password}" and TOTP "{totp_code}"'))
def when_user_logs_in_with_totp(client, context, enrolled_user, password, totp_code):
    """POST /auth/login with an explicit TOTP code."""
    context["response"] = client.post(
        "/auth/login",
        json={
            "email": enrolled_user["email"],
            "password": password,
            "totp_code": totp_code,
        },
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


@then("the response requires TOTP enrollment")
def then_response_requires_totp_enrollment(context):
    """Assert the login response includes a TOTP secret and provisioning URI."""
    response = context["response"]
    assert response.status_code == 200
    data = response.json()
    assert data["enrollment_required"] is True
    assert data["secret"]
    assert data["provisioning_uri"]


@then("the user has a TOTP secret")
def then_user_has_totp_secret(provisioned_tenant, data_dir, enrolled_user):
    """Verify the database user row now stores a TOTP secret."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT totp_secret, totp_enrolled FROM users WHERE id = ?",
            (enrolled_user["id"],),
        )
        row = cur.fetchone()
        assert row[0] is not None
    finally:
        conn.close()


@then("a session is created")
def then_a_session_is_created(provisioned_tenant, data_dir, enrolled_user, context):
    """Verify the login response contains a session token persisted in the DB."""
    response = context["response"]
    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?",
            (enrolled_user["id"],),
        )
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()


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


@then("a failed login attempt is recorded")
def then_failed_login_attempt_recorded(provisioned_tenant, data_dir, enrolled_user):
    """Verify the user's failed_attempts counter has increased."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT failed_attempts FROM users WHERE id = ?",
            (enrolled_user["id"],),
        )
        assert cur.fetchone()[0] == 1
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


@when("the user requests a password reset")
@when("the user requests a password reset again")
def when_user_requests_password_reset(client, context, enrolled_user):
    """POST /auth/password-reset-request with the user's email."""
    context["response"] = client.post(
        "/auth/password-reset-request",
        json={"email": enrolled_user["email"]},
    )


@then("a reset email with a token is sent")
def then_reset_email_with_token_sent(context):
    """Verify the console backend captured a reset email containing a token."""
    from app.services.email_backends import get_sent_messages

    messages = get_sent_messages()
    assert len(messages) >= 1
    last = messages[-1]
    assert "password reset" in last["subject"].lower()
    assert "token=" in last["body"]
    token = last["body"].split("token=")[1].split()[0]
    context["reset_token"] = token


@when(parsers.parse('the user resets the password using the token to "{new_password}"'))
def when_user_resets_password(client, context, new_password):
    """POST /auth/password-reset with the captured token and new password."""
    context["response"] = client.post(
        "/auth/password-reset",
        json={"token": context["reset_token"], "new_password": new_password},
    )


@then(parsers.parse('the user\'s password is "{password}"'))
def then_user_password_is(provisioned_tenant, data_dir, enrolled_user, password):
    """Verify the stored password hash matches the given plaintext."""
    from app.services.auth import verify_password

    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (enrolled_user["id"],),
        )
        row = cur.fetchone()
        assert verify_password(password, row[0]) is True
    finally:
        conn.close()


@when("31 minutes pass")
def when_31_minutes_pass(context):
    """Advance freezegun time by 31 minutes and keep the freezer for cleanup."""
    from freezegun import freeze_time

    future = datetime.now(UTC) + timedelta(minutes=31)
    freezer = freeze_time(future)
    freezer.start()
    context["freezer"] = freezer


@when(
    parsers.parse(
        'the user tries to reset the password using the expired token to "{new_password}"'
    )
)
def when_user_tries_expired_reset(client, context, new_password):
    """POST /auth/password-reset with the expired token."""
    context["response"] = client.post(
        "/auth/password-reset",
        json={"token": context["reset_token"], "new_password": new_password},
    )
    if "freezer" in context:
        context["freezer"].stop()
        del context["freezer"]


@then("the reset is rejected as expired")
def then_reset_rejected_expired(context):
    """Assert the reset endpoint rejected the expired token."""
    response = context["response"]
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"
