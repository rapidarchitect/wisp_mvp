"""Shared fixtures and Gherkin step definitions for pytest-bdd."""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers

from app.ai.fakes import FakeLLM
from app.api.routers.auth import router as auth_router
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


@given(parsers.parse('"{email}" is signed in'))
def given_user_signed_in(client, context, email):
    """Log in the named user and store the session token."""
    import pyotp

    user = next((u for u in [context.get("admin")] if u and u["email"] == email), None)
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
    parsers.parse('an enrolled user "{email}" with password "{password}"'),
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
