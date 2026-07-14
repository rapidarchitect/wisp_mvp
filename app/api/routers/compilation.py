"""Compilation and submission API router (Task 14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user
from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.compilation import compile_domain, submit_domain

router = APIRouter()


@router.post("/domains/{code}/compile")
async def compile_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
    llm: Any | None = None,
) -> dict:
    """Compile the contributor's answers into a domain narrative."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await compile_domain(db, contributor_id=user["id"], code=code, llm=llm)


@router.post("/domains/{code}/submit")
async def submit_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """Submit a compiled domain for reviewer approval."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await submit_domain(db, contributor_id=user["id"], code=code)
