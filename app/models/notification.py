"""Pydantic models for notification endpoints."""

from pydantic import BaseModel, Field


class NotificationListParams(BaseModel):
    """Query parameters for the notifications feed."""

    unread_only: bool = Field(default=False)
