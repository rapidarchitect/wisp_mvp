"""Review workflow API router (Task 15)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user
from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.review import approve_domain, defer_domain, revise_and_approve

router = APIRouter()


@router.post("/domains/{code}/approve")
async def approve_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """Approve a submitted domain."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await approve_domain(db, reviewer_id=user["id"], code=code)


@router.post("/domains/{code}/revise")
async def revise_domain_endpoint(
    request: Request,
    code: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    llm: Any | None = None,
) -> dict:
    """Revise the compiled narrative and immediately approve the domain."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await revise_and_approve(
        db,
        reviewer_id=user["id"],
        code=code,
        revision_prompt=payload["revision_prompt"],
        llm=llm,
    )


@router.post("/domains/{code}/defer")
async def defer_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """Defer a submitted domain back to the contributor."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await defer_domain(db, reviewer_id=user["id"], code=code)
