"""Notification feed API router (Task 11)."""

from fastapi import APIRouter, Header, Query, Request

from app.api.dependencies import get_current_user
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.notifications import get_notifications, mark_read

router = APIRouter()


@router.get("")
async def list_notifications(
    request: Request,
    unread_only: bool = Query(default=False),
    authorization: str = Header(...),
) -> list[dict]:
    """Return the current user's notification feed."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await get_notifications(db, user["id"], unread_only=unread_only)


@router.post("/{notification_id}/read")
async def read_notification(
    request: Request,
    notification_id: int,
    authorization: str = Header(...),
) -> dict:
    """Mark a notification as read."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await mark_read(db, notification_id, user["id"])
