"""Authentication API router (Task 03)."""

from fastapi import APIRouter, Header, Request

from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.auth import LoginRequest, SessionResponse
from app.services.audit import audit
from app.services.auth import (
    create_session,
    get_user_by_email,
    get_user_from_session,
    is_account_locked,
    record_failed_login,
    reset_failed_attempts,
    verify_password,
)

router = APIRouter()


@router.post("/login")
async def login(request: Request, payload: LoginRequest) -> SessionResponse:
    """Authenticate with email and password (TOTP added in Task 04).

    Returns a session token on success. On failure returns 401 with an error
    code of either `invalid_credentials` or `account_locked`.
    """
    db = get_tenant_db_from_request(request)

    user = await get_user_by_email(db, payload.email)
    if user is None:
        raise AuthorizationError("Invalid credentials", code="invalid_credentials")

    if await is_account_locked(user):
        raise AuthorizationError("Account locked", code="account_locked")

    if not verify_password(payload.password, user["password_hash"]):
        await record_failed_login(db, user)
        await audit(
            db,
            actor_user_id=user["id"],
            event_type="login_failed",
            subject=payload.email,
            detail="invalid_credentials",
        )
        raise AuthorizationError("Invalid credentials", code="invalid_credentials")

    await reset_failed_attempts(db, user["id"])
    token = await create_session(db, user["id"])
    await audit(
        db,
        actor_user_id=user["id"],
        event_type="login_succeeded",
        subject=payload.email,
    )
    return SessionResponse(token=token)


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
