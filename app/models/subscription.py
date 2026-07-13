"""Pydantic models for subscriptions."""

from pydantic import BaseModel


class Subscription(BaseModel):
    """A tenant's subscription record."""

    id: int
    tenant_id: int
    tier: str
    funding: str
    stripe_customer_id: str | None = None
    stripe_checkout_id: str | None = None
    voucher_code: str | None = None
    status: str
