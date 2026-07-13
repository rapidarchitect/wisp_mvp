"""Tests for tenant provisioning and lookup services."""

import pytest

from app.db.tenant import tenant_db_path
from app.exceptions import NotFoundError
from app.models.tenant import SubscriptionFunding, TenantStatus
from app.services.tenant import (
    create_tenant_record,
    get_tenant_by_slug,
    provision_tenant,
    tenant_exists,
)


@pytest.fixture
async def control_db_path(tmp_path):
    """Create an initialized control DB and return its path."""
    from app.db.control import init_control_db

    path = tmp_path / "control.db"
    conn = await init_control_db(path)
    await conn.close()
    return path


async def test_create_tenant_record(control_db_path, tmp_path):
    """Creating a tenant record inserts into the control DB."""
    tenant = await create_tenant_record(
        control_db_path,
        "acme",
        "Acme CPA",
        SubscriptionFunding.CARD,
    )
    assert tenant.slug == "acme"
    assert tenant.status == TenantStatus.PROVISIONING


async def test_get_tenant_by_slug(control_db_path, tmp_path):
    """A tenant can be looked up by slug."""
    await create_tenant_record(
        control_db_path,
        "acme",
        "Acme CPA",
        SubscriptionFunding.VOUCHER,
        voucher_code="ACME-123",
    )
    tenant = await get_tenant_by_slug(control_db_path, "acme")
    assert tenant.slug == "acme"
    assert tenant.company_name == "Acme CPA"


async def test_get_tenant_by_slug_not_found(control_db_path):
    """An unknown slug raises NotFoundError (C-01)."""
    with pytest.raises(NotFoundError):
        await get_tenant_by_slug(control_db_path, "missing")


async def test_provision_tenant_creates_db_file(control_db_path, tmp_path):
    """Provisioning creates both the control record and the tenant SQLite file."""
    tenant = await provision_tenant(
        control_db_path,
        tmp_path,
        "acme",
        "Acme CPA",
        SubscriptionFunding.CARD,
    )
    assert tenant.status == TenantStatus.ACTIVE
    assert await tenant_exists(tmp_path, "acme")
    assert tenant_db_path(tmp_path, "acme").exists()


async def test_provisioned_tenants_are_isolated(control_db_path, tmp_path):
    """C-01: provisioned tenants have separate DB files."""
    await provision_tenant(control_db_path, tmp_path, "acme", "Acme CPA", SubscriptionFunding.CARD)
    await provision_tenant(
        control_db_path, tmp_path, "widgets", "Widgets LLC", SubscriptionFunding.VOUCHER
    )

    assert tenant_db_path(tmp_path, "acme").exists()
    assert tenant_db_path(tmp_path, "widgets").exists()
    assert tenant_db_path(tmp_path, "acme") != tenant_db_path(tmp_path, "widgets")
