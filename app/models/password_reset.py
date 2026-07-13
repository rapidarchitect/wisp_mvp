"""Pydantic models for password reset payloads."""

from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    """Request a password reset email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm a password reset with a signed token."""

    token: str
    new_password: str = Field(min_length=12)
