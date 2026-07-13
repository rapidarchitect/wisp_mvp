"""Pydantic models for user management."""

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """User summary returned by list endpoints."""

    id: int
    email: EmailStr
    roles: list[str]
    status: str
