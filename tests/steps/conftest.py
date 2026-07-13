"""Shared fixtures and Gherkin step definitions for pytest-bdd."""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers

from app.api.routers.auth import router as auth_router
from app.api.routers.signup import router as signup_router
from app.api.routers.users import router as users_router
from app.db.control import init_control_db
from app.db.tenant import init_tenant_db
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


@pytest.fixture
def control_db_path(data_dir):
    """Path to a freshly initialized control-plane database."""
    import asyncio

    path = data_dir / "control.db"
    asyncio.run(init_control_db(path))
    return path


@pytest.fixture
def provisioned_tenant(control_db_path, data_dir, tenant_slug):
    """Create a control-plane tenant record and initialize its SQLite file."""
    import asyncio

    conn = sqlite3.connect(control_db_path)
    try:
        conn.execute(
            "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
            (tenant_slug, "Palmetto Tax", "active"),
        )
        conn.commit()
    finally:
        conn.close()
    asyncio.run(init_tenant_db(data_dir, tenant_slug))
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
def app(data_dir, control_db_path):
    """FastAPI test app with tenant middleware, auth router, and error handlers."""
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
