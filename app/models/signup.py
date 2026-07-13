"""Pydantic models for signup payloads."""

from pydantic import BaseModel, EmailStr, Field


class CorporateVitalsInput(BaseModel):
    """Required firm description collected during signup."""

    employee_range: str
    clients_per_year_range: str
    primary_software: str
    deployment_type: str
    has_efin: bool
    it_support_provider: str | None = None
    remote_access: bool
    paper_files: bool
    sensitive_data_types: list[str] = Field(default_factory=list)
    coordinator_name: str
    coordinator_title: str


class SignupRequest(BaseModel):
    """Visitor signup request."""

    company_name: str
    address: str
    workspace_email: EmailStr
    funding: str = Field(pattern=r"^(card|voucher)$")
    voucher_code: str | None = None
    vitals: CorporateVitalsInput


class WebhookRequest(BaseModel):
    """Synthetic Stripe webhook payload used in tests."""

    event: str
    checkout_id: str
