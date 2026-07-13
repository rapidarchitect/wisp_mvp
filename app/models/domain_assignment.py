"""Pydantic models for domain assignment endpoints."""

from pydantic import BaseModel, EmailStr


class AssignDomainRequest(BaseModel):
    """Payload for assigning a contributor and reviewer to a domain."""

    contributor_email: EmailStr
    reviewer_email: EmailStr
