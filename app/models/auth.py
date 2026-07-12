"""Pydantic models for authentication payloads."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Email + password login payload (TOTP added in Task 04)."""

    email: EmailStr
    password: str = Field(min_length=12)
    totp_code: str | None = None


class SessionResponse(BaseModel):
    """Session token returned after successful authentication."""

    token: str


class AuthErrorResponse(BaseModel):
    """JSON error body for authentication failures."""

    code: str
    message: str
