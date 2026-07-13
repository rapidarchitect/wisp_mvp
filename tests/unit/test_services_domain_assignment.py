"""Unit tests for domain assignment services."""

import orjson
import pytest  # noqa: F401

from app.db.tenant import init_tenant_db
from app.exceptions import (  # noqa: F401
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.services.domain_assignment import assign_domain


async def _seed_version(db):
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    return (await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1"))[0]


async def _seed_domain(db, version_id, code="AC", status="ready"):
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        (code, "Access Control", version_id, status),
    )
    await db.commit()


async def _seed_user(db, email, roles, status="active"):
    cur = await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, "hash", orjson.dumps(roles), status, 0, 1),
    )
    await db.commit()
    return cur.lastrowid


async def test_assign_domain_success(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    contributor_id = await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    reviewer_id = await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    result = await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    assert result["code"] == "AC"
    assert result["contributor_id"] == contributor_id
    assert result["reviewer_id"] == reviewer_id
    status = (await db.fetchone("SELECT status FROM domains WHERE code = 'AC'"))[0]
    assert status == "assigned"
    await db.close()


async def test_assign_domain_notifies_new_users(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    rows = await db.fetchall("SELECT type, user_id FROM notifications ORDER BY id")
    types = [r["type"] for r in rows]
    assert "domain_assigned" in types
    assert len(rows) == 2
    await db.close()


async def test_assign_domain_replacement_notifies_displaced_users(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c1@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r1@acme.app.wisp.llc", ["reviewer"])
    await _seed_user(db, "c2@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r2@acme.app.wisp.llc", ["reviewer"])

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c1@acme.app.wisp.llc",
        reviewer_email="r1@acme.app.wisp.llc",
    )
    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c2@acme.app.wisp.llc",
        reviewer_email="r2@acme.app.wisp.llc",
    )

    rows = await db.fetchall("SELECT type, user_id FROM notifications ORDER BY id")
    types = [r["type"] for r in rows]
    assert types.count("domain_unassigned") == 2
    assert types.count("domain_assigned") == 4
    await db.close()
