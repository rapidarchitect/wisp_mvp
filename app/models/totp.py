"""Pydantic models for TOTP payloads."""

from pydantic import BaseModel


class TotpEnrollmentResponse(BaseModel):
    """TOTP enrollment details returned on first login."""

    enrollment_required: bool = True
    secret: str
    provisioning_uri: str


class TotpLoginRequest(BaseModel):
    """Login payload that includes a TOTP code."""

    email: str
    password: str
    totp_code: str
