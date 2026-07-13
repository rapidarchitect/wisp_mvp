"""Authentication API router (Task 03 + 04 + 05)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Header, Request

from app.config import settings
from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.auth import LoginRequest, SessionResponse
from app.models.password_reset import PasswordResetConfirm, PasswordResetRequest
from app.models.totp import TotpEnrollmentResponse
from app.services.auth import get_user_by_email, get_user_from_session, login
from app.services.email_backends import ConsoleEmailBackend
from app.services.password_reset import create_reset_token, reset_password, verify_reset_token

router = APIRouter()


def _get_email_backend():
    """Return the configured email backend instance."""
    if settings.email_backend == "console":
        return ConsoleEmailBackend()
    # SES backend will be added in Task 11.
    raise RuntimeError(f"Unknown email backend: {settings.email_backend}")


@router.post("/login")
async def auth_login(
    request: Request,
    payload: LoginRequest,
) -> SessionResponse | TotpEnrollmentResponse:
    """Authenticate with email and password; TOTP required once enrolled.

    - First login for a user returns TOTP enrollment details (C-04).
    - Subsequent logins require a valid TOTP code.
    - Failures return 401 with code `invalid_credentials` or `account_locked`.
    """
    db = get_tenant_db_from_request(request)
    result = await login(db, payload.email, payload.password, payload.totp_code)

    if result["status"] == "enrollment_required":
        return TotpEnrollmentResponse(
            enrollment_required=True,
            secret=result["secret"],
            provisioning_uri=result["provisioning_uri"],
        )
    return SessionResponse(token=result["token"])


@router.post("/password-reset-request")
async def password_reset_request(request: Request, payload: PasswordResetRequest) -> dict:
    """Send a password reset email with a signed 30-minute token (C-06)."""
    db = get_tenant_db_from_request(request)
    user = await get_user_by_email(db, payload.email)
    if user is None:
        # Do not reveal whether the email exists.
        return {"sent": True}

    token = create_reset_token(
        user["id"],
        payload.email,
        datetime.now(UTC),
        settings.secret_key,
    )
    backend = _get_email_backend()
    await backend.send(
        to=payload.email,
        subject="WISPGen password reset",
        body=(
            f"Use the following link to reset your password:\n"
            f"https://{request.headers.get('host', settings.base_domain)}"
            f"/auth/password-reset?token={token}\n"
            f"This link expires in 30 minutes."
        ),
    )
    return {"sent": True}


@router.post("/password-reset")
async def password_reset_confirm(request: Request, payload: PasswordResetConfirm) -> dict:
    """Reset a user's password using a signed token."""
    db = get_tenant_db_from_request(request)
    user_id = verify_reset_token(
        payload.token,
        settings.secret_key,
        datetime.now(UTC),
    )
    await reset_password(db, user_id, payload.new_password)
    return {"reset": True}


@router.get("/me")
async def me(request: Request, authorization: str = Header(...)) -> dict:
    """Return the current session's user.

    Requires an `Authorization: Bearer <token>` header. Expired or missing
    tokens return 401 with code `session_expired`.
    """
    db = get_tenant_db_from_request(request)

    if not authorization.lower().startswith("bearer "):
        raise AuthorizationError("Session expired", code="session_expired")

    token = authorization[7:].strip()
    user = await get_user_from_session(db, token)
    if user is None:
        raise AuthorizationError("Session expired", code="session_expired")

    return {
        "id": user["id"],
        "email": user["email"],
        "roles": user["roles"],
        "status": user["status"],
    }
