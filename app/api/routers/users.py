"""User and invitation management API router (Task 07)."""

from fastapi import APIRouter, Header, HTTPException, Request

from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.invitation import AcceptInvitationRequest, InvitationRequest, SetRolesRequest
from app.services.auth import get_user_from_session
from app.services.invitations import accept_invitation, invite_user
from app.services.users import deactivate_user, list_users, set_roles

router = APIRouter()


def _roles_list(roles_str: str) -> list[str]:
    return [r.strip() for r in roles_str.split(",")]


async def _get_current_user(request: Request, authorization: str):
    db = get_tenant_db_from_request(request)
    if not authorization.lower().startswith("bearer "):
        raise AuthorizationError("Session expired", code="session_expired")
    token = authorization[7:].strip()
    user = await get_user_from_session(db, token)
    if user is None:
        raise AuthorizationError("Session expired", code="session_expired")
    return user


def _require_admin(user: dict) -> None:
    roles = user["roles"]
    if "admin" not in roles:
        raise AuthorizationError("Admin role required", code="forbidden")


@router.get("")
async def users_list(request: Request, authorization: str = Header(...)) -> list[dict]:
    """List users in the current tenant."""
    await _get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await list_users(db)


@router.post("/invite")
async def users_invite(
    request: Request,
    payload: InvitationRequest,
    authorization: str = Header(...),
) -> dict:
    """Invite a new user with one or more roles."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await invite_user(
        db,
        invited_by_user_id=actor["id"],
        email=payload.email,
        roles=_roles_list(payload.roles),
    )


@router.post("/accept")
async def users_accept(request: Request, payload: AcceptInvitationRequest) -> dict:
    """Accept an invitation and create an active user."""
    db = get_tenant_db_from_request(request)
    return await accept_invitation(
        db,
        token=payload.token,
        password=payload.password,
        totp_secret=payload.totp_secret,
    )


@router.post("/{user_id}/roles")
async def users_set_roles(
    request: Request,
    user_id: int,
    payload: SetRolesRequest,
    authorization: str = Header(...),
) -> dict:
    """Replace roles for a user."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    target = await _get_user_by_id(db, user_id)
    return await set_roles(
        db,
        actor_user_id=actor["id"],
        target_email=target["email"],
        roles=_roles_list(payload.roles),
    )


@router.post("/{user_id}/deactivate")
async def users_deactivate(
    request: Request,
    user_id: int,
    authorization: str = Header(...),
) -> dict:
    """Deactivate a user and unassign their domains."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    target = await _get_user_by_id(db, user_id)
    return await deactivate_user(
        db,
        actor_user_id=actor["id"],
        target_email=target["email"],
    )


async def _get_user_by_id(db, user_id: int) -> dict:
    row = await db.fetchone(
        "SELECT id, email FROM users WHERE id = ?",
        (user_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)
