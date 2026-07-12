"""Authentication API router (Task 03 + 04)."""

from fastapi import APIRouter, Header, Request

from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.auth import LoginRequest, SessionResponse
from app.models.totp import TotpEnrollmentResponse
from app.services.auth import get_user_from_session, login

router = APIRouter()


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
