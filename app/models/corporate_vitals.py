"""Pydantic models for corporate vitals."""

from pydantic import BaseModel


class CorporateVitals(BaseModel):
    """Stored corporate vitals for a tenant."""

    employee_range: str
    clients_per_year_range: str
    primary_software: str
    deployment_type: str
    has_efin: bool
    it_support_provider: str | None
    remote_access: bool
    paper_files: bool
    sensitive_data_types: list[str]
    coordinator_name: str
    coordinator_title: str
