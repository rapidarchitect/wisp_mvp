"""Pydantic models for WISP versions."""

from pydantic import BaseModel


class WISPVersion(BaseModel):
    """A versioned WISP document for a tenant."""

    id: int
    tenant_id: int
    number: int
    status: str
    created_at: str
    completed_at: str | None = None
    parent_version_id: int | None = None
