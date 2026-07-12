"""Tests for the per-tenant SQLite database factory."""

import pytest

from app.db.tenant import get_tenant_db, init_tenant_db, tenant_db_path


@pytest.fixture
async def tenant_factory(tmp_path):
    """Return a helper that creates initialized tenant DBs in tmp_path."""

    async def _create(slug: str):
        return await init_tenant_db(tmp_path, slug)

    return _create


async def test_tenant_db_path(tenant_factory, tmp_path):
    """The tenant DB file path includes the slug."""
    path = tenant_db_path(tmp_path, "acme")
    assert path.name == "acme.db"
    assert path.parent.name == "tenants"


async def test_init_tenant_db_creates_schema(tenant_factory):
    """All expected tenant tables exist after initialization."""
    db = await tenant_factory("acme")
    try:
        for table in (
            "corporate_vitals",
            "users",
            "invitations",
            "sessions",
            "wisp_versions",
            "domains",
            "questions",
            "answers",
            "followups",
            "compiled_answers",
            "domain_assignments",
            "notifications",
            "audit_events",
        ):
            row = await db.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            assert row is not None, f"missing table {table}"
            assert row[0] == table
    finally:
        await db.close()


async def test_two_tenants_do_not_share_data(tenant_factory, tmp_path):
    """C-01: rows written in tenant A are invisible to tenant B."""
    acme = await tenant_factory("acme")
    widgets = await tenant_factory("widgets")
    try:
        await acme.execute(
            "INSERT INTO users (email, password_hash, status) VALUES (?, ?, ?)",
            ("a@acme.com", "hash", "active"),
        )
        await acme.commit()

        acme_rows = await acme.fetchall("SELECT email FROM users")
        widget_rows = await widgets.fetchall("SELECT email FROM users")

        assert [r["email"] for r in acme_rows] == ["a@acme.com"]
        assert widget_rows == []
    finally:
        await acme.close()
        await widgets.close()


async def test_tenant_db_files_are_separate(tenant_factory, tmp_path):
    """Each tenant gets a distinct SQLite file on disk."""
    acme = await tenant_factory("acme")
    widgets = await tenant_factory("widgets")
    await acme.close()
    await widgets.close()

    assert tenant_db_path(tmp_path, "acme") != tenant_db_path(tmp_path, "widgets")
    assert tenant_db_path(tmp_path, "acme").exists()
    assert tenant_db_path(tmp_path, "widgets").exists()


async def test_get_tenant_db_without_init_has_no_tables(tmp_path):
    """get_tenant_db creates the file but does not apply the schema."""
    db = await get_tenant_db(tmp_path, "empty")
    try:
        row = await db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert row is None
    finally:
        await db.close()
