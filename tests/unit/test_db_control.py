"""Tests for the control-plane database."""

import pytest

from app.db.control import close_connection, fetchone, get_control_db, init_control_db
from app.models.tenant import SubscriptionFunding


@pytest.fixture
async def control_db(tmp_path):
    """Yield an initialized control DB connected to a temporary file."""
    path = tmp_path / "control.db"
    conn = await init_control_db(path)
    try:
        yield conn
    finally:
        await close_connection(conn)


async def test_init_control_db_creates_tenants_table(control_db):
    """The tenants table exists after initialization."""
    row = await fetchone(
        control_db,
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'",
    )
    assert row["name"] == "tenants"


async def test_init_control_db_creates_subscriptions_and_vouchers(control_db):
    """Subscriptions and vouchers tables exist after initialization."""
    for table in ("subscriptions", "vouchers"):
        row = await fetchone(
            control_db,
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        assert row["name"] == table


async def test_insert_tenant_and_subscription(control_db):
    """Tenants and subscriptions can be inserted and queried."""
    cursor = await control_db.execute(
        "INSERT INTO tenants (slug, company_name, status) VALUES (?, ?, ?)",
        ("demo", "Demo Firm", "active"),
    )
    tenant_id = cursor.lastrowid
    await control_db.execute(
        "INSERT INTO vouchers (code, issued_to, expires_at) VALUES (?, ?, ?)",
        ("DEMO-123", "ops@example.com", "2027-01-01T00:00:00"),
    )
    await control_db.execute(
        "INSERT INTO subscriptions (tenant_id, funding, voucher_code, status) VALUES (?, ?, ?, ?)",
        (tenant_id, SubscriptionFunding.VOUCHER.value, "DEMO-123", "active"),
    )
    await control_db.commit()

    row = await fetchone(
        control_db,
        "SELECT t.slug, s.funding, v.code "
        "FROM tenants t "
        "JOIN subscriptions s ON s.tenant_id = t.id "
        "JOIN vouchers v ON v.code = s.voucher_code "
        "WHERE t.slug = ?",
        ("demo",),
    )
    assert row["slug"] == "demo"
    assert row["funding"] == "voucher"
    assert row["code"] == "DEMO-123"


async def test_get_control_db_creates_parent_directory(tmp_path):
    """get_control_db creates parent directories if needed."""
    path = tmp_path / "nested" / "control.db"
    conn = await get_control_db(path)
    try:
        assert path.exists()
    finally:
        await close_connection(conn)
