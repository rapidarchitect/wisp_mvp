"""WISP version and export API router (Task 16)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import Response

from app.api.dependencies import get_current_user
from app.db.tenant import TenantDB
from app.exceptions import AuthorizationError, NotFoundError
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.pdf import render_wisp_pdf
from app.services.versions import (
    get_current_version,
    list_versions,
    start_new_version,
)

router = APIRouter()


def _get_company_name(request: Request) -> str:
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        return tenant.company_name or ""
    return ""


def _get_tenant_id(request: Request) -> int:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise AuthorizationError("Tenant context required", code="tenant_not_found")
    return tenant.id


def _require_auth(authorization: str | None) -> str:
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    return authorization


@router.get("/versions")
async def get_versions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> list[dict]:
    """List WISP versions for the tenant."""
    await get_current_user(request, _require_auth(authorization))
    db = get_tenant_db_from_request(request)
    return await list_versions(db, tenant_id=_get_tenant_id(request))


@router.get("/versions/current/export")
async def export_current_version(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    """Export the current WISP version as a PDF."""
    await get_current_user(request, _require_auth(authorization))
    db = get_tenant_db_from_request(request)
    version = await get_current_version(db, tenant_id=_get_tenant_id(request))
    company_name = _get_company_name(request)
    include_draft = version["status"] != "complete"  # C-13
    pdf_bytes = await render_wisp_pdf(
        db,
        version["id"],
        company_name=company_name,
        include_draft=include_draft,
    )
    filename = f"wisp-v{version['number']}-{version['status']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/versions/{version_number}/export")
async def export_version_by_number(
    request: Request,
    version_number: int,
    authorization: str | None = Header(default=None),
) -> Response:
    """Export a specific WISP version as a PDF."""
    await get_current_user(request, _require_auth(authorization))
    db = get_tenant_db_from_request(request)
    versions = await list_versions(db, tenant_id=_get_tenant_id(request))
    version = next((v for v in versions if v["number"] == version_number), None)
    if version is None:
        raise NotFoundError(f"version {version_number} not found")
    company_name = _get_company_name(request)
    include_draft = version["status"] != "complete"  # C-13
    pdf_bytes = await render_wisp_pdf(
        db,
        version["id"],
        company_name=company_name,
        include_draft=include_draft,
    )
    filename = f"wisp-v{version['number']}-{version['status']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/versions")
async def create_version(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    """Start a new WISP version from the approved baseline of the previous one."""
    user = await get_current_user(request, _require_auth(authorization))
    db: TenantDB = get_tenant_db_from_request(request)
    result = await start_new_version(
        db,
        tenant_id=_get_tenant_id(request),
        created_by_user_id=user["id"],
    )
    return result
