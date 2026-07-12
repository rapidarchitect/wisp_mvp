"""Tests for subdomain-based tenant resolution middleware."""

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.tenancy import TenantMiddleware, resolve_subdomain


def _make_request(host: str) -> Request:
    """Build a minimal ASGI request with the given Host header."""
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", host.encode())],
            "client": None,
            "server": ("testserver", 80),
            "state": {},
        }
    )


@pytest.mark.parametrize(
    ("host", "base", "expected"),
    [
        ("demo.app.wisp.llc", "app.wisp.llc", "demo"),
        ("demo.app.wisp.llc:8000", "app.wisp.llc", "demo"),
        ("demo.localhost", "localhost", "demo"),
        ("demo.localhost:5173", "localhost", "demo"),
        ("app.wisp.llc", "app.wisp.llc", None),
        ("localhost", "localhost", None),
        ("unknown.example.com", "app.wisp.llc", None),
    ],
)
def test_resolve_subdomain(host, base, expected):
    """resolve_subdomain extracts slugs correctly for dev and prod domains."""
    assert resolve_subdomain(host, base) == expected


async def test_middleware_attaches_tenant_state(tmp_path):
    """The middleware attaches tenant slug and DB to request.state."""
    from app.db.control import close_connection, init_control_db
    from app.db.tenant import init_tenant_db

    control_path = tmp_path / "control.db"
    conn = await init_control_db(control_path)
    await conn.execute(
        "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
        ("acme", "Acme CPA", "active"),
    )
    await conn.commit()
    await close_connection(conn)

    await init_tenant_db(tmp_path, "acme")

    middleware = TenantMiddleware(None, control_db_path=control_path, data_dir=tmp_path)

    async def call_next(request: Request) -> Response:
        assert request.state.tenant_slug == "acme"
        assert request.state.tenant_db is not None
        return Response('{"ok": true}', media_type="application/json")

    request = _make_request("acme.app.wisp.llc")
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200


async def test_middleware_returns_404_for_unknown_tenant(tmp_path):
    """An unknown subdomain returns a branded 404 JSON response."""
    from app.db.control import init_control_db

    control_path = tmp_path / "control.db"
    await init_control_db(control_path)

    middleware = TenantMiddleware(None, control_db_path=control_path, data_dir=tmp_path)

    async def call_next(request: Request) -> Response:
        return Response('{"ok": true}', media_type="application/json")

    request = _make_request("unknown.app.wisp.llc")
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 404
    assert b"tenant_not_found" in response.body


async def test_middleware_apex_domain_has_no_tenant(tmp_path):
    """Requests to the apex domain have no tenant context."""
    from app.db.control import init_control_db

    control_path = tmp_path / "control.db"
    await init_control_db(control_path)

    middleware = TenantMiddleware(None, control_db_path=control_path, data_dir=tmp_path)

    async def call_next(request: Request) -> Response:
        assert request.state.tenant_slug is None
        assert request.state.tenant_db is None
        return Response('{"ok": true}', media_type="application/json")

    request = _make_request("app.wisp.llc")
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
