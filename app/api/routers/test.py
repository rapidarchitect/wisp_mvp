"""Test-only endpoints for frontend E2E support. Disabled outside test mode."""

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.auth import hash_password

router = APIRouter()


def _require_test_mode():
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/invitations")
async def list_invitations(request: Request, email: str | None = None) -> list[dict]:
    """Return invitations so E2E tests can extract activation tokens."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    if email:
        rows = await db.fetchall(
            "SELECT email, roles, token, expires_at, accepted_at FROM invitations WHERE email = ?",
            (email,),
        )
    else:
        rows = await db.fetchall(
            """
            SELECT email, roles, token, expires_at, accepted_at
            FROM invitations
            ORDER BY id DESC LIMIT 10
            """
        )
    return [dict(row) for row in rows]


@router.post("/users")
async def create_test_user(request: Request, payload: dict) -> dict:
    """Create a user directly for E2E seeding."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    await db.execute(
        """
        INSERT INTO users (
            email, password_hash, roles, status, totp_secret, totp_enrolled, failed_attempts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["email"],
            hash_password(payload["password"]),
            payload.get("roles", '["contributor"]'),
            payload.get("status", "active"),
            payload.get("totp_secret"),
            1 if payload.get("totp_enrolled", True) else 0,
            0,
        ),
    )
    await db.commit()
    return {"created": True}
