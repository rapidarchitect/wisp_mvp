"""Password reset token and password update service."""

import base64
import hmac
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.exceptions import AuthorizationError

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


def create_reset_token(user_id: int, email: str, now: datetime, secret_key: str) -> str:
    """Create a signed 30-minute password reset token."""
    expires_at = now + timedelta(minutes=30)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expires_at.isoformat(),
    }
    data = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(secret_key.encode(), data.encode(), "sha256").hexdigest()
    return f"{data}.{signature}"


def verify_reset_token(
    token: str,
    secret_key: str,
    now: datetime,
    max_age_minutes: int = 30,
) -> int:
    """Verify a reset token and return the user_id, or raise AuthorizationError."""
    try:
        data_b64, signature = token.rsplit(".", 1)
    except ValueError as exc:
        raise AuthorizationError("Invalid reset token", code="token_expired") from exc

    expected = hmac.new(secret_key.encode(), data_b64.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise AuthorizationError("Invalid reset token", code="token_expired")

    payload = json.loads(base64.urlsafe_b64decode(data_b64))
    expires_at = datetime.fromisoformat(payload["exp"])
    if now > expires_at:
        raise AuthorizationError("Reset token expired", code="token_expired")

    # Defense in depth: also enforce max_age even if the client clock drifts.
    issued_at = expires_at - timedelta(minutes=max_age_minutes)
    if now < issued_at:
        raise AuthorizationError("Reset token expired", code="token_expired")

    return payload["user_id"]


async def reset_password(db: "TenantDB", user_id: int, new_password: str) -> None:
    """Update the user's password hash after token verification."""
    from app.services.auth import hash_password, validate_password

    validate_password(new_password)
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user_id),
    )
    await db.commit()
