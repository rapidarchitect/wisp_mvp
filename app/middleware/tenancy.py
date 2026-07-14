"""Subdomain-based tenant resolution middleware."""

from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings
from app.db.tenant import TenantDB, get_tenant_db
from app.exceptions import NotFoundError
from app.services.tenant import get_tenant_by_slug


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve the tenant from the request Host header and attach it to request.state.

    Enforces C-01: tenant identity comes from the resolved subdomain only.
    """

    def __init__(self, app, control_db_path: str | Path, data_dir: str | Path) -> None:
        super().__init__(app)
        self.control_db_path = Path(control_db_path)
        self.data_dir = Path(data_dir)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = request.headers.get("host", "")
        slug = resolve_subdomain(host, settings.base_domain)

        if slug is None:
            # Requests to the apex domain have no tenant context.
            request.state.tenant_slug = None
            request.state.tenant_db = None
            return await call_next(request)

        # Signup routes target the to-be-created workspace subdomain and must
        # not require an existing tenant record. Both the legacy root mount and
        # the /api/v1 prefix used by the React frontend are allowed.
        if request.url.path.startswith("/signup") or request.url.path.startswith("/api/v1/signup"):
            request.state.tenant = None
            request.state.tenant_slug = slug
            request.state.tenant_db = None
            return await call_next(request)

        try:
            tenant = await get_tenant_by_slug(self.control_db_path, slug)
        except NotFoundError:
            return Response(
                content='{"error": {"code": "tenant_not_found", "message": "Workspace not found"}}',
                status_code=404,
                media_type="application/json",
            )

        tenant_db = await get_tenant_db(self.data_dir, slug)
        try:
            request.state.tenant = tenant
            request.state.tenant_slug = tenant.slug
            request.state.tenant_db = tenant_db
            response = await call_next(request)
        finally:
            await tenant_db.close()

        return response


def resolve_subdomain(host: str, base_domain: str) -> str | None:
    """Extract the subdomain slug from a Host header.

    Examples:
        - demo.app.wisp.llc, base app.wisp.llc -> demo
        - demo.localhost, base localhost -> demo
        - app.wisp.llc, base app.wisp.llc -> None (apex)
        - localhost, base localhost -> None (apex)
    """
    host = host.split(":")[0].lower().strip()
    base = base_domain.lower().strip()

    if host == base:
        return None

    if host.endswith(f".{base}"):
        return host[: -(len(base) + 1)]

    # Dev convenience: *.localhost handling when base_domain is localhost.
    if base == "localhost" and "." in host:
        return host.split(".")[0]

    return None


def get_tenant_db_from_request(request: Request) -> TenantDB:
    """Return the tenant DB handle attached by the middleware.

    Raises RuntimeError if the middleware has not run.
    """
    tenant_db = getattr(request.state, "tenant_db", None)
    if tenant_db is None:
        raise RuntimeError("TenantMiddleware has not attached a tenant_db to this request")
    return tenant_db
