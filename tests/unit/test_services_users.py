"""Unit tests for user and role management services."""

import json

import pytest

from app.db.tenant import init_tenant_db
from app.exceptions import NotFoundError
from app.services.auth import hash_password
from app.services.users import deactivate_user, list_users, set_roles


async def _seed_admin(db):
    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "admin@acme.app.wisp.llc",
            hash_password("AdminPass123!"),
            json.dumps(["admin"]),
            "active",
            0,
            0,
        ),
    )
    await db.commit()


async def test_list_users(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_admin(tenant_db)
    await tenant_db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "jane@acme.app.wisp.llc",
            hash_password("Pass12345678!"),
            json.dumps(["contributor"]),
            "active",
            0,
            0,
        ),
    )
    await tenant_db.commit()

    users = await list_users(tenant_db)

    assert len(users) == 2
    assert {u["email"] for u in users} == {"admin@acme.app.wisp.llc", "jane@acme.app.wisp.llc"}
    await tenant_db.close()


async def test_set_roles(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_admin(tenant_db)
    await tenant_db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("multi@acme.app.wisp.llc", hash_password("Pass12345678!"), json.dumps([]), "active", 0, 0),
    )
    await tenant_db.commit()

    result = await set_roles(
        tenant_db,
        actor_user_id=1,
        target_email="multi@acme.app.wisp.llc",
        roles=["admin", "contributor", "reviewer"],
    )

    assert result["roles"] == ["admin", "contributor", "reviewer"]
    row = await tenant_db.fetchone(
        "SELECT roles FROM users WHERE email = ?",
        ("multi@acme.app.wisp.llc",),
    )
    assert json.loads(row["roles"]) == ["admin", "contributor", "reviewer"]
    await tenant_db.close()


async def test_set_roles_unknown_user_raises(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_admin(tenant_db)

    with pytest.raises(NotFoundError):
        await set_roles(
            tenant_db,
            actor_user_id=1,
            target_email="ghost@acme.app.wisp.llc",
            roles=["contributor"],
        )

    await tenant_db.close()


async def test_deactivate_user_unassigns_domains(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_admin(tenant_db)
    await tenant_db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "deac@acme.app.wisp.llc",
            hash_password("Pass12345678!"),
            json.dumps(["contributor", "reviewer"]),
            "active",
            0,
            0,
        ),
    )
    await tenant_db.commit()
    await tenant_db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    version_id = (await tenant_db.execute("SELECT last_insert_rowid()")).lastrowid
    await tenant_db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "assigned"),
    )
    domain_id = (await tenant_db.execute("SELECT last_insert_rowid()")).lastrowid
    await tenant_db.execute(
        """
        INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
        VALUES (?, ?, ?)
        """,
        (domain_id, 2, 1),
    )
    await tenant_db.commit()

    result = await deactivate_user(
        tenant_db,
        actor_user_id=1,
        target_email="deac@acme.app.wisp.llc",
    )

    assert result["status"] == "deactivated"
    row = await tenant_db.fetchone(
        "SELECT status FROM users WHERE email = ?",
        ("deac@acme.app.wisp.llc",),
    )
    assert row["status"] == "deactivated"

    domain = await tenant_db.fetchone(
        "SELECT status FROM domains WHERE id = ?",
        (domain_id,),
    )
    assert domain["status"] == "pending_questions"

    assignments = await tenant_db.fetchall(
        "SELECT * FROM domain_assignments WHERE domain_id = ?",
        (domain_id,),
    )
    assert len(assignments) == 0
    await tenant_db.close()
