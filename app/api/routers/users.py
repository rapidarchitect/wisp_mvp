"""User and invitation management API router (Task 07)."""

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.dependencies import get_current_user, require_admin
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.invitation import AcceptInvitationRequest, InvitationRequest, SetRolesRequest
from app.services.invitations import accept_invitation, invite_user
from app.services.users import deactivate_user, list_users, set_roles

router = APIRouter()


def _roles_list(roles_str: str) -> list[str]:
    return [r.strip() for r in roles_str.split(",")]


@router.get("")
async def users_list(request: Request, authorization: str = Header(...)) -> list[dict]:
    """List users in the current tenant."""
    await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await list_users(db)


@router.get("/invitations")
async def users_invitations_list(request: Request, authorization: str = Header(...)) -> list[dict]:
    """List pending invitations in the current tenant."""
    require_admin(await get_current_user(request, authorization))
    db = get_tenant_db_from_request(request)
    rows = await db.fetchall(
        """
        SELECT email, roles, token, expires_at, accepted_at
        FROM invitations
        WHERE accepted_at IS NULL
        ORDER BY expires_at DESC
        """
    )
    return [dict(row) for row in rows]


@router.post("/invite")
async def users_invite(
    request: Request,
    payload: InvitationRequest,
    authorization: str = Header(...),
) -> dict:
    """Invite a new user with one or more roles."""
    actor = await get_current_user(request, authorization)
    require_admin(actor)
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
    actor = await get_current_user(request, authorization)
    require_admin(actor)
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
    actor = await get_current_user(request, authorization)
    require_admin(actor)
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
