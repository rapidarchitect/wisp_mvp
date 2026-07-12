"""Pydantic models for control-plane and tenant entities."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TenantStatus(StrEnum):
    """Lifecycle status of a tenant workspace."""

    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class SubscriptionFunding(StrEnum):
    """How a subscription is funded."""

    CARD = "card"
    VOUCHER = "voucher"


class SubscriptionStatus(StrEnum):
    """Status of a subscription."""

    ACTIVE = "active"
    CANCELED = "canceled"


class Tenant(BaseModel):
    """A provisioned firm workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    company_name: str
    address: str | None = None
    logo_path: str | None = None
    status: TenantStatus = TenantStatus.PROVISIONING
    created_at: datetime


class Subscription(BaseModel):
    """Payment subscription for a tenant."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    tier: str = "standard"
    funding: SubscriptionFunding
    stripe_customer_id: str | None = None
    stripe_checkout_id: str | None = None
    voucher_code: str | None = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    started_at: datetime


class Voucher(BaseModel):
    """A voucher that can fully replace card payment (C-17)."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    issued_to: str
    redeemed_by_tenant_id: int | None = None
    redeemed_at: datetime | None = None
    expires_at: datetime
