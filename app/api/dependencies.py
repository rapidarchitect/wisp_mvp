"""Shared API dependencies."""

from fastapi import Request

from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.auth import get_user_from_session


async def get_current_user(request: Request, authorization: str) -> dict:
    """Resolve a bearer token to the current user."""
    db = get_tenant_db_from_request(request)
    if not authorization.lower().startswith("bearer "):
        raise AuthorizationError("Session expired", code="session_expired")
    token = authorization[7:].strip()
    user = await get_user_from_session(db, token)
    if user is None:
        raise AuthorizationError("Session expired", code="session_expired")
    return user


def require_admin(user: dict) -> None:
    """Raise if the user does not have the admin role."""
    roles = user["roles"]
    if "admin" not in roles:
        raise AuthorizationError("Admin role required", code="forbidden")
