"""Pydantic models for question management endpoints."""

from pydantic import BaseModel, Field


class AddQuestionRequest(BaseModel):
    """Payload for adding a custom admin question to a domain."""

    domain_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    position: int | None = Field(None, ge=0)


class EditQuestionRequest(BaseModel):
    """Payload for editing question text."""

    text: str = Field(..., min_length=1)
