"""Unit tests for WISP version lifecycle service."""

from __future__ import annotations

import pytest

from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError
from app.services.versions import get_current_version, list_versions, start_new_version


async def _seed_first_version(db, *, status: str = "in_progress"):
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("c@test.com", "x", '["contributor"]', "active", "s", 1),
    )
    contributor_id = (await db.fetchone("SELECT id FROM users"))["id"]
    reviewer_id = contributor_id
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, status),
    )
    version_id = (await db.fetchone("SELECT id FROM wisp_versions"))["id"]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "approved"),
    )
    domain_id = (await db.fetchone("SELECT id FROM domains"))["id"]
    await db.execute(
        "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) VALUES (?, ?, ?)",
        (domain_id, "Compiled.", "2026-01-01T00:00:00"),
    )
    await db.execute(
        "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)",
        (domain_id, contributor_id, reviewer_id),
    )
    await db.commit()
    return version_id


@pytest.mark.asyncio
async def test_start_new_version_clones_approved_baseline(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        await _seed_first_version(db, status="complete")
        result = await start_new_version(db, tenant_id=1, created_by_user_id=1)
        versions = await list_versions(db, tenant_id=1)
    finally:
        await db.close()

    assert result["number"] == 2
    assert result["status"] == "in_progress"
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_start_new_version_rejects_when_in_progress(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        await _seed_first_version(db, status="in_progress")
        with pytest.raises(ConflictError) as exc_info:
            await start_new_version(db, tenant_id=1, created_by_user_id=1)
        assert exc_info.value.code == "version_in_progress"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_get_current_version_returns_latest(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        await _seed_first_version(db, status="complete")
        await start_new_version(db, tenant_id=1, created_by_user_id=1)
        current = await get_current_version(db, tenant_id=1)
    finally:
        await db.close()

    assert current["number"] == 2
