"""Tenant lookup and provisioning services."""

from pathlib import Path

from app.db.control import close_connection, fetchall, fetchone, get_control_db
from app.db.tenant import init_tenant_db, tenant_db_path
from app.exceptions import NotFoundError
from app.models.tenant import SubscriptionFunding, SubscriptionStatus, Tenant, TenantStatus


async def get_tenant_by_slug(
    control_db_path: str | Path,
    slug: str,
) -> Tenant:
    """Look up a tenant by subdomain slug in the control DB.

    Raises NotFoundError if the slug does not exist (C-01).
    """
    conn = await get_control_db(control_db_path)
    try:
        row = await fetchone(
            conn,
            "SELECT id, slug, company_name, address, logo_path, status, created_at "
            "FROM tenants WHERE slug = ?",
            (slug,),
        )
    finally:
        await close_connection(conn)

    if row is None:
        raise NotFoundError(f"tenant '{slug}' not found")

    return Tenant.model_validate(dict(row))


async def create_tenant_record(
    control_db_path: str | Path,
    slug: str,
    company_name: str,
    funding: SubscriptionFunding,
    voucher_code: str | None = None,
) -> Tenant:
    """Create the control-plane records for a new tenant and provision its DB file."""
    conn = await get_control_db(control_db_path)
    try:
        cursor = await conn.execute(
            "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
            (slug, company_name, TenantStatus.PROVISIONING.value),
        )
        tenant_id = cursor.lastrowid
        await conn.execute(
            "INSERT INTO subscriptions (tenant_id, funding, voucher_code, status) "
            "VALUES (?, ?, ?, ?)",
            (tenant_id, funding.value, voucher_code, SubscriptionStatus.ACTIVE.value),
        )
        await conn.commit()
        row = await fetchone(
            conn,
            "SELECT id, slug, company_name, address, logo_path, status, created_at "
            "FROM tenants WHERE id = ?",
            (tenant_id,),
        )
    finally:
        await close_connection(conn)

    tenant = Tenant.model_validate(dict(row))
    return tenant


async def provision_tenant(
    control_db_path: str | Path,
    data_dir: str | Path,
    slug: str,
    company_name: str,
    funding: SubscriptionFunding,
    voucher_code: str | None = None,
) -> Tenant:
    """Create the control record and the tenant SQLite file for a new firm."""
    tenant = await create_tenant_record(control_db_path, slug, company_name, funding, voucher_code)
    tenant_db = await init_tenant_db(data_dir, slug)
    await tenant_db.close()

    conn = await get_control_db(control_db_path)
    try:
        await conn.execute(
            "UPDATE tenants SET status = ? WHERE id = ?",
            (TenantStatus.ACTIVE.value, tenant.id),
        )
        await conn.commit()
        row = await fetchone(
            conn,
            "SELECT id, slug, company_name, address, logo_path, status, created_at "
            "FROM tenants WHERE id = ?",
            (tenant.id,),
        )
    finally:
        await close_connection(conn)

    return Tenant.model_validate(dict(row))


async def tenant_exists(data_dir: str | Path, slug: str) -> bool:
    """Return True if the tenant's SQLite file exists."""
    return tenant_db_path(data_dir, slug).exists()


async def list_tenants(control_db_path: str | Path) -> list[Tenant]:
    """Return all tenants from the control DB."""
    conn = await get_control_db(control_db_path)
    try:
        rows = await fetchall(
            conn,
            "SELECT id, slug, company_name, address, logo_path, status, created_at FROM tenants",
        )
    finally:
        await close_connection(conn)
    return [Tenant.model_validate(dict(row)) for row in rows]
