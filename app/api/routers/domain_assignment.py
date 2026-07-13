"""Domain assignment API router (Task 12)."""

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user, require_admin
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.domain_assignment import AssignDomainRequest
from app.services.domain_assignment import (
    assign_domain,
    get_unassigned_domains,
    list_user_assignments,
)

router = APIRouter()


@router.post("/{code}/assign")
async def assign_domain_endpoint(
    request: Request,
    code: str,
    payload: AssignDomainRequest,
    authorization: str = Header(...),
) -> dict:
    """Assign a contributor and reviewer to a domain (admin only)."""
    actor = await get_current_user(request, authorization)
    require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await assign_domain(
        db,
        actor_user_id=actor["id"],
        code=code,
        contributor_email=payload.contributor_email,
        reviewer_email=payload.reviewer_email,
    )


@router.get("/unassigned")
async def list_unassigned_domains(
    request: Request,
    authorization: str = Header(...),
) -> list[dict]:
    """List domains missing an assignment (admin only)."""
    actor = await get_current_user(request, authorization)
    require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await get_unassigned_domains(db)


@router.get("/assigned")
async def list_my_assignments(
    request: Request,
    authorization: str = Header(...),
) -> list[dict]:
    """List domains assigned to the current user."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await list_user_assignments(db, user_id=user["id"])
