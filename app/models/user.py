"""Pydantic models for user entities."""

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """A user within a tenant workspace."""

    id: int
    email: EmailStr
    roles: set[str] = Field(default_factory=set)
    status: str
    totp_enrolled: bool = False
