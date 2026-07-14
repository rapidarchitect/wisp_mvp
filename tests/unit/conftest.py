"""Fixtures for unit-level router tests."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.fakes import FakeLLM
from app.api.routers.auth import router as auth_router
from app.api.routers.compilation import router as compilation_router
from app.api.routers.domain_assignment import router as domain_assignment_router
from app.api.routers.notifications import router as notifications_router
from app.api.routers.questionnaire import router as questionnaire_router
from app.api.routers.questions import domain_router
from app.api.routers.questions import router as questions_router
from app.api.routers.signup import router as signup_router
from app.api.routers.users import router as users_router
from app.db.control import init_control_db
from app.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    WispgenError,
)
from app.middleware.tenancy import TenantMiddleware
from app.services.payment import FakeStripeClient


def _error_response(code: str, message: str, status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def control_db_path(data_dir):
    import asyncio

    path = data_dir / "control.db"
    asyncio.run(init_control_db(path))
    return path


@pytest.fixture
def provisioned_tenant(control_db_path, data_dir):
    """Create a control-plane tenant record and provision it."""
    import asyncio

    from app.db.control import get_control_db
    from app.services.provisioning import provision_tenant

    slug = "palmetto"
    conn = sqlite3.connect(control_db_path)
    try:
        conn.execute(
            "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
            (slug, "Palmetto Tax", "active"),
        )
        conn.commit()
        tenant_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()

    async def _provision():
        control_db = await get_control_db(control_db_path)
        try:
            await provision_tenant(control_db, tenant_id=tenant_id, slug=slug, data_dir=data_dir)
        finally:
            await control_db.close()

    asyncio.run(_provision())
    return slug


@pytest.fixture
def app(data_dir, control_db_path, monkeypatch):
    """FastAPI test app with all routers including compilation."""
    from app.crews import seeder_crew

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
    application.include_router(questionnaire_router, tags=["questionnaire"])
    application.include_router(compilation_router, tags=["compilation"])
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
        status = 403 if exc.code == "forbidden" else 401
        return _error_response(exc.code, str(exc), status)

    @application.exception_handler(ConflictError)
    async def conflict_error_handler(request, exc):
        return _error_response(getattr(exc, "code", "conflict"), str(exc), 409)

    @application.exception_handler(WispgenError)
    async def wispgen_error_handler(request, exc):
        return _error_response("internal_error", str(exc), 500)

    return application


@pytest.fixture
def client(app, provisioned_tenant):
    return TestClient(app, base_url="http://palmetto.app.wisp.llc")


@pytest.fixture
def context():
    return {}


@pytest.fixture
def provisioned_user(provisioned_tenant, data_dir):
    """Create a contributor user with TOTP enrolled."""
    from app.services.auth import hash_password
    from app.services.totp import generate_totp_secret

    email = "contributor@palmetto.app.wisp.llc"
    password = "SecurePass123!"
    secret = generate_totp_secret()
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                email,
                hash_password(password),
                '["contributor"]',
                "active",
                secret,
                1,
            ),
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    return {"id": user_id, "email": email, "password": password, "totp_secret": secret}


@pytest.fixture
def session_token(client, provisioned_user):
    """Sign in the provisioned user and return the session token."""
    import pyotp

    totp = pyotp.TOTP(provisioned_user["totp_secret"])
    response = client.post(
        "/auth/login",
        json={
            "email": provisioned_user["email"],
            "password": provisioned_user["password"],
            "totp_code": totp.now(),
        },
    )
    assert response.status_code == 200
    return response.json()["token"]
