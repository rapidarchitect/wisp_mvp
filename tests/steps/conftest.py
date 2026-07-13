"""Shared fixtures and Gherkin step definitions for pytest-bdd."""

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, then, when

from app.ai.fakes import FakeLLM
from app.api.routers.auth import router as auth_router
from app.api.routers.domain_assignment import router as domain_assignment_router
from app.api.routers.notifications import router as notifications_router
from app.api.routers.questions import domain_router
from app.api.routers.questions import router as questions_router
from app.api.routers.signup import router as signup_router
from app.api.routers.users import router as users_router
from app.db.control import init_control_db
from app.middleware.tenancy import TenantMiddleware
from app.services.payment import FakeStripeClient


@pytest.fixture
def data_dir(tmp_path):
    """Root data directory for the test tenant."""
    return tmp_path


@given(parsers.parse('a provisioned tenant "{slug}"'), target_fixture="tenant_slug")
def given_provisioned_tenant(slug):
    """Set the tenant slug expected by the provisioned_tenant fixture."""
    return slug


@given(parsers.parse('an enrolled admin "{email}" with password "{password}"'))
def given_enrolled_admin(provisioned_tenant, data_dir, email, password, context):
    """Create an admin user with TOTP enrolled and store credentials."""
    import json

    from app.services.auth import hash_password
    from app.services.totp import generate_totp_secret

    secret = generate_totp_secret()
    path = data_dir / "tenants" / f"{provisioned_tenant}.db"
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
                json.dumps(["admin"]),
                "active",
                secret,
                1,
                0,
            ),
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    context["admin"] = {"id": user_id, "email": email, "password": password, "totp_secret": secret}
    context.setdefault("users", {})[email] = context["admin"]


@given(parsers.parse('"{email}" is signed in'))
@when(parsers.parse('"{email}" is signed in'))
def given_user_signed_in(client, context, email):
    """Log in the named user and store the session token."""
    import pyotp

    user = context.get("admin") if context.get("admin", {}).get("email") == email else None
    if user is None:
        user = context.get("users", {}).get(email)
    assert user is not None, f"No credentials for {email}"
    totp = pyotp.TOTP(user["totp_secret"])
    response = client.post(
        "/auth/login",
        json={"email": email, "password": user["password"], "totp_code": totp.now()},
    )
    assert response.status_code == 200
    context["session_token"] = response.json()["token"]


@pytest.fixture
def control_db_path(data_dir):
    """Path to a freshly initialized control-plane database."""
    import asyncio

    path = data_dir / "control.db"
    asyncio.run(init_control_db(path))
    return path


@pytest.fixture
def provisioned_tenant(control_db_path, data_dir, tenant_slug):
    """Create a control-plane tenant record and provision it (schema + 14 empty domains)."""
    import asyncio

    from app.db.control import get_control_db
    from app.services.provisioning import provision_tenant

    conn = sqlite3.connect(control_db_path)
    try:
        conn.execute(
            "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
            (tenant_slug, "Palmetto Tax", "active"),
        )
        conn.commit()
        tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()

    async def _provision():
        control_db = await get_control_db(control_db_path)
        try:
            await provision_tenant(
                control_db,
                tenant_id=tenant_id,
                slug=tenant_slug,
                data_dir=data_dir,
            )
        finally:
            await control_db.close()

    asyncio.run(_provision())
    return tenant_slug


@given(
    parsers.re(r'^an enrolled user "(?P<email>[^"]+)" with password "(?P<password>[^"]+)"$'),
    target_fixture="enrolled_user",
)
def given_enrolled_user(provisioned_tenant, data_dir, email, password):
    """Create a user in the tenant database with the given credentials."""
    from app.services.auth import hash_password

    path = data_dir / "tenants" / f"{provisioned_tenant}.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, hash_password(password), '["admin"]', "active", 0, 0),
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": user_id, "email": email, "password": password}
    finally:
        conn.close()


def _error_response(code: str, message: str, status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@pytest.fixture
def app(data_dir, control_db_path, monkeypatch):
    """FastAPI test app with tenant middleware, all routers, and error handlers."""
    from app.crews import seeder_crew
    from app.exceptions import (
        AuthorizationError,
        ConflictError,
        NotFoundError,
        ValidationError,
        WispgenError,
    )

    application = FastAPI()
    application.state.control_db_path = data_dir / "control.db"
    application.state.data_dir = data_dir
    application.state.stripe_client = FakeStripeClient("succeed")
    application.add_middleware(
        TenantMiddleware,
        control_db_path=data_dir / "control.db",
        data_dir=data_dir,
    )
    application.include_router(auth_router, prefix="/auth", tags=["auth"])
    application.include_router(signup_router, prefix="/signup", tags=["signup"])
    application.include_router(users_router, prefix="/users", tags=["users"])
    application.include_router(questions_router, prefix="/questions", tags=["questions"])
    application.include_router(domain_router, prefix="/domains", tags=["domains"])
    application.include_router(domain_assignment_router, prefix="/domains", tags=["domains"])
    application.include_router(
        notifications_router, prefix="/notifications", tags=["notifications"]
    )

    fake_llm = FakeLLM(
        default='{"questions": ['
        '{"text": "A?"}, {"text": "B?"}, {"text": "C?"}, '
        '{"text": "D?"}, {"text": "E?"}, {"text": "F?"}'
        "]}"
    )
    monkeypatch.setattr(seeder_crew, "create_llm", lambda _provider=None: fake_llm)

    @application.exception_handler(ValidationError)
    async def validation_error_handler(request, exc):
        return _error_response(getattr(exc, "code", "validation_error"), str(exc), 422)

    @application.exception_handler(NotFoundError)
    async def not_found_error_handler(request, exc):
        return _error_response("not_found", str(exc), 404)

    @application.exception_handler(AuthorizationError)
    async def authorization_error_handler(request, exc):
        return _error_response(exc.code, str(exc), 401)

    @application.exception_handler(ConflictError)
    async def conflict_error_handler(request, exc):
        return _error_response(getattr(exc, "code", "conflict"), str(exc), 409)

    @application.exception_handler(WispgenError)
    async def wispgen_error_handler(request, exc):
        return _error_response("internal_error", str(exc), 500)

    return application


@pytest.fixture
def client(app):
    """Synchronous HTTP client targeting the palmetto subdomain."""
    return TestClient(app, base_url="http://palmetto.app.wisp.llc")


@pytest.fixture
def context():
    """Mutable dict for passing state between pytest-bdd steps."""
    return {}


@pytest.fixture(autouse=True)
def _clear_captured_emails():
    """Reset the console email backend before every BDD scenario."""
    from app.services.email_backends import clear_sent_messages

    clear_sent_messages()
    yield


def _tenant_db_path(data_dir: Path, slug: str) -> Path:
    return data_dir / "tenants" / f"{slug}.db"


def _roles_list(roles_str: str) -> list[str]:
    return [r.strip() for r in roles_str.split(",")]


@given(
    parsers.re(
        r'^an enrolled user "(?P<email>[^"]+)" with password "(?P<password>[^"]+)" '
        r'and roles "(?P<roles>[^"]+)"$'
    )
)
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
