"""Unit tests for invitation services."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.invitations import accept_invitation, invite_user


async def _seed_user(db, email="admin@acme.app.wisp.llc"):
    from app.services.auth import hash_password

    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, hash_password("AdminPass123!"), '["admin"]', "active", 0, 0),
    )
    await db.commit()


async def test_invite_user_creates_token(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_user(tenant_db)
    result = await invite_user(
        tenant_db,
        invited_by_user_id=1,
        email="jane@acme.app.wisp.llc",
        roles=["contributor"],
    )

    assert result["email"] == "jane@acme.app.wisp.llc"
    assert result["roles"] == ["contributor"]
    assert "token" in result

    row = await tenant_db.fetchone(
        "SELECT expires_at FROM invitations WHERE token = ?",
        (result["token"],),
    )
    expires_at = datetime.fromisoformat(row["expires_at"])
    delta = expires_at - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)
    await tenant_db.close()


async def test_invite_user_duplicate_raises(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_user(tenant_db)
    await invite_user(
        tenant_db,
        invited_by_user_id=1,
        email="jane@acme.app.wisp.llc",
        roles=["contributor"],
    )

    with pytest.raises(ConflictError) as exc_info:
        await invite_user(
            tenant_db,
            invited_by_user_id=1,
            email="jane@acme.app.wisp.llc",
            roles=["reviewer"],
        )

    assert exc_info.value.code == "duplicate_invitation"
    await tenant_db.close()


async def test_accept_invitation_creates_user(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_user(tenant_db)
    invitation = await invite_user(
        tenant_db,
        invited_by_user_id=1,
        email="jane@acme.app.wisp.llc",
        roles=["contributor", "reviewer"],
    )

    result = await accept_invitation(
        tenant_db,
        token=invitation["token"],
        password="SecurePass123!",
        totp_secret="JBSWY3DPEHPK3PXP",
    )

    assert result["email"] == "jane@acme.app.wisp.llc"
    assert result["roles"] == ["contributor", "reviewer"]

    user = await tenant_db.fetchone(
        "SELECT roles, totp_enrolled FROM users WHERE email = ?",
        (result["email"],),
    )
    assert json.loads(user["roles"]) == ["contributor", "reviewer"]
    assert user["totp_enrolled"] == 1
    await tenant_db.close()


async def test_accept_invitation_expired_raises(tmp_path):
    from freezegun import freeze_time

    tenant_db = await init_tenant_db(tmp_path, "acme")
    await _seed_user(tenant_db)
    with freeze_time("2026-01-01"):
        invitation = await invite_user(
            tenant_db,
            invited_by_user_id=1,
            email="jane@acme.app.wisp.llc",
            roles=["contributor"],
        )

    with pytest.raises(ValidationError) as exc_info, freeze_time("2026-01-10"):
        await accept_invitation(
            tenant_db,
            token=invitation["token"],
            password="SecurePass123!",
            totp_secret="JBSWY3DPEHPK3PXP",
        )

    assert exc_info.value.code == "invitation_expired"
    await tenant_db.close()


async def test_accept_invitation_unknown_token_raises(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")

    with pytest.raises(NotFoundError):
        await accept_invitation(
            tenant_db,
            token="invalid-token",
            password="SecurePass123!",
            totp_secret="JBSWY3DPEHPK3PXP",
        )

    await tenant_db.close()
