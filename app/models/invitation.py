"""Pydantic models for user invitations."""

from pydantic import BaseModel, EmailStr, Field


class InvitationRequest(BaseModel):
    """Admin invitation request."""

    email: EmailStr
    roles: str = Field(pattern=r"^(admin|contributor|reviewer)(,(admin|contributor|reviewer))*$")


class AcceptInvitationRequest(BaseModel):
    """Invitation acceptance request."""

    token: str = Field(min_length=1)
    password: str = Field(min_length=12)
    totp_secret: str = Field(min_length=1)


class SetRolesRequest(BaseModel):
    """Role update request."""

    roles: str = Field(pattern=r"^(admin|contributor|reviewer)(,(admin|contributor|reviewer))*$")
