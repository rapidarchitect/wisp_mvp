"""Invitation lifecycle services."""

import json
import secrets
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.email_backends import get_email_backend


async def invite_user(
    db: TenantDB,
    *,
    invited_by_user_id: int,
    email: str,
    roles: list[str],
) -> dict:
    """Create a 7-day invitation token for a new user."""
    existing = await db.fetchone(
        """
        SELECT token FROM invitations
        WHERE email = ? AND accepted_at IS NULL AND expires_at > ?
        """,
        (email, datetime.now(UTC).isoformat()),
    )
    if existing is not None:
        raise ConflictError("An active invitation already exists", code="duplicate_invitation")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=7)
    await db.execute(
        """
        INSERT INTO invitations (email, roles, token, expires_at, invited_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            email,
            json.dumps(roles),
            token,
            expires_at.isoformat(),
            invited_by_user_id,
        ),
    )
    await db.commit()
    activation_url = f"https://{db.slug}.{settings.base_domain}/activate?token={token}"
    backend = get_email_backend()
    await backend.send(
        to=email,
        subject="You have been invited to WISPGen",
        body=f"Click to activate your account: {activation_url}",
    )
    return {"token": token, "email": email, "roles": roles}


async def accept_invitation(
    db: TenantDB,
    *,
    token: str,
    password: str,
    totp_secret: str,
) -> dict:
    """Create an active user from a valid invitation token."""
    from app.services.auth import hash_password

    row = await db.fetchone(
        """
        SELECT email, roles, expires_at, accepted_at FROM invitations WHERE token = ?
        """,
        (token,),
    )
    if row is None:
        raise NotFoundError("Invitation not found")
    if row["accepted_at"] is not None:
        raise ConflictError("Invitation already accepted", code="invitation_used")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(UTC):
        raise ValidationError("Invitation has expired", code="invitation_expired")

    existing_user = await db.fetchone(
        "SELECT id FROM users WHERE email = ?",
        (row["email"],),
    )
    if existing_user is not None:
        raise ConflictError("User already exists", code="user_exists")

    await db.execute(
        """
        INSERT INTO users
            (email, password_hash, roles, status, totp_secret, totp_enrolled, failed_attempts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["email"],
            hash_password(password),
            row["roles"],
            "active",
            totp_secret,
            1,
            0,
        ),
    )
    await db.execute(
        "UPDATE invitations SET accepted_at = ? WHERE token = ?",
        (datetime.now(UTC).isoformat(), token),
    )
    await db.commit()
    return {"email": row["email"], "roles": json.loads(row["roles"])}
