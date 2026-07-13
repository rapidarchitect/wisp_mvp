"""Audit log service for tenant-scoped events."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


async def audit(
    db: "TenantDB",
    *,
    actor_user_id: int | None,
    event_type: str,
    subject: str,
    detail: str | None = None,
) -> None:
    """Persist an audit event in the tenant database.

    Args:
        db: Tenant database connection.
        actor_user_id: User who caused the event, or None for anonymous/unauthenticated.
        event_type: Short event category, e.g. "login_failed" or "domain_approved".
        subject: Entity the event concerns, e.g. an email or domain code.
        detail: Optional human-readable detail. Must never contain answer text or secrets.
    """
    await db.execute(
        """
        INSERT INTO audit_events (actor_user_id, event_type, subject, detail, at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            actor_user_id,
            event_type,
            subject,
            detail or "",
            datetime.now(UTC).isoformat(),
        ),
    )
    await db.commit()
