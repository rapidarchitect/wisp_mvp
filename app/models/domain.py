"""Pydantic models for WISP domains."""

from pydantic import BaseModel


class Domain(BaseModel):
    """One of the 14 NIST-style security domains in a WISP version."""

    id: int
    code: str
    name: str
    wisp_version_id: int
    status: str
