"""Notification service: in-app feed and transactional email dispatch."""

from datetime import UTC, datetime

import orjson

from app.db.tenant import TenantDB
from app.exceptions import NotFoundError, ValidationError
from app.services.email_backends import get_email_backend
from app.services.notification_templates import render


async def notify(
    db: TenantDB,
    *,
    user_id: int,
    kind: str,
    payload: dict,
    channel: str = "both",
) -> dict:
    """Create a notification and optionally send an email."""
    if channel not in ("in_app", "email", "both"):
        raise ValidationError("channel must be in_app, email, or both", code="invalid_channel")

    try:
        subject, body = render(kind, payload)
    except KeyError as exc:
        raise ValidationError(f"Unknown notification kind: {kind}", code="unknown_kind") from exc

    user = await db.fetchone(
        "SELECT id, email FROM users WHERE id = ?",
        (user_id,),
    )
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    cursor = await db.execute(
        """
        INSERT INTO notifications (user_id, type, payload, channel)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, kind, orjson.dumps(payload).decode("utf-8"), channel),
    )
    notification_id = cursor.lastrowid
    sent_at: str | None = None

    if channel in ("email", "both"):
        backend = get_email_backend()
        await backend.send(to=user["email"], subject=subject, body=body)
        sent_at = datetime.now(UTC).isoformat()
        await db.execute(
            "UPDATE notifications SET sent_at = ? WHERE id = ?",
            (sent_at, notification_id),
        )

    await db.commit()
    return {
        "notification_id": notification_id,
        "user_id": user_id,
        "kind": kind,
        "channel": channel,
        "sent_at": sent_at,
    }


async def get_notifications(
    db: TenantDB,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Return the user's notification feed, newest first."""
    sql = """
        SELECT id, type, payload, channel, read_at, sent_at
        FROM notifications
        WHERE user_id = ?
    """
    params: list = [user_id]
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = await db.fetchall(sql, tuple(params))
    return [dict(row) for row in rows]


async def mark_read(
    db: TenantDB,
    notification_id: int,
    user_id: int,
) -> dict:
    """Mark a single notification as read."""
    row = await db.fetchone(
        "SELECT user_id FROM notifications WHERE id = ?",
        (notification_id,),
    )
    if row is None or row["user_id"] != user_id:
        raise NotFoundError(f"Notification {notification_id} not found")

    read_at = datetime.now(UTC).isoformat()
    await db.execute(
        "UPDATE notifications SET read_at = ? WHERE id = ?",
        (read_at, notification_id),
    )
    await db.commit()
    return {"notification_id": notification_id, "read_at": read_at}
