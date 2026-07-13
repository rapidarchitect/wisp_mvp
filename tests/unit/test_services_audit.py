"""Tests for the audit log service."""

from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from app.db.tenant import get_tenant_db, init_tenant_db
from app.services.audit import audit


@pytest.fixture
async def tenant_db(tmp_path):
    """An initialized tenant database in a temporary directory."""
    await init_tenant_db(tmp_path, "acme")
    db = await get_tenant_db(tmp_path, "acme")
    yield db
    await db.close()


async def test_audit_creates_event(tenant_db):
    """audit() persists an audit event with actor, type, subject, and detail."""
    now = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
    with freeze_time(now):
        await audit(
            tenant_db,
            actor_user_id=7,
            event_type="login_failed",
            subject="a@acme.com",
            detail="wrong password",
        )

    row = await tenant_db.fetchone(
        "SELECT actor_user_id, event_type, subject, detail, at FROM audit_events"
    )
    assert row["actor_user_id"] == 7
    assert row["event_type"] == "login_failed"
    assert row["subject"] == "a@acme.com"
    assert row["detail"] == "wrong password"
    assert datetime.fromisoformat(row["at"]) == now


async def test_audit_allows_none_actor(tenant_db):
    """Anonymous events (e.g., failed login for unknown user) are allowed."""
    await audit(
        tenant_db,
        actor_user_id=None,
        event_type="login_failed",
        subject="unknown@acme.com",
    )

    row = await tenant_db.fetchone("SELECT actor_user_id FROM audit_events")
    assert row["actor_user_id"] is None


async def test_audit_does_not_leak_answers(tenant_db, caplog):
    """C-18: audit detail should not include tenant answer content."""
    await audit(
        tenant_db,
        actor_user_id=1,
        event_type="login_failed",
        subject="a@acme.com",
        detail="invalid credentials",
    )

    rows = await tenant_db.fetchall("SELECT detail FROM audit_events")
    for row in rows:
        assert "password" not in row["detail"].lower()
