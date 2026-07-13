"""Pydantic models for vouchers."""

from pydantic import BaseModel
from pydantic import Field as PydanticField


class Voucher(BaseModel):
    """A prepaid voucher that can fully fund a subscription."""

    code: str = PydanticField(min_length=1)
    issued_to: str | None = None
    redeemed_by_tenant_id: int | None = None
    redeemed_at: str | None = None
    expires_at: str | None = None
