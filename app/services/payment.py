"""Payment abstraction and fake Stripe client for tests."""

from dataclasses import dataclass

from app.exceptions import ExternalServiceError, ValidationError


class PaymentError(ExternalServiceError):
    """Payment processing failed."""


@dataclass
class CheckoutSession:
    id: str
    url: str | None
    status: str


class FakeStripeClient:
    """In-memory Stripe stand-in used in BDD and unit tests.

    mode:
        - "succeed": create_checkout_session returns a completed session.
        - "decline": create_checkout_session raises PaymentError.
    """

    _counter = 0

    def __init__(self, mode: str = "succeed") -> None:
        self.mode = mode

    async def create_checkout_session(
        self, *, amount_cents: int, tenant_slug: str
    ) -> CheckoutSession:
        """Create a fake checkout session for a tenant."""
        if self.mode == "decline":
            raise PaymentError("Your card was declined.")
        FakeStripeClient._counter += 1
        checkout_id = f"cs_test_{tenant_slug}_{FakeStripeClient._counter}"
        return CheckoutSession(
            id=checkout_id,
            url=f"https://checkout.stripe.test/{checkout_id}",
            status="open",
        )

    async def get_checkout_session(self, checkout_id: str) -> CheckoutSession:
        """Retrieve a fake checkout session by id."""
        if self.mode == "decline":
            raise PaymentError("Your card was declined.")
        return CheckoutSession(id=checkout_id, url=None, status="complete")


def get_default_stripe_client() -> FakeStripeClient:
    """Return the production-mode Stripe client.

    For the scaffold this is the same fake client; a real Stripe integration
    would return an httpx-based client using STRIPE_SECRET_KEY.
    """
    return FakeStripeClient("succeed")


async def validate_voucher(control_db, code: str) -> bool:
    """Return True if the voucher exists, is not expired, and is not redeemed."""
    from datetime import UTC, datetime

    from app.db.control import fetchone

    row = await fetchone(
        control_db,
        "SELECT redeemed_by_tenant_id, expires_at FROM vouchers WHERE code = ?",
        (code,),
    )
    if row is None:
        raise ValidationError("voucher_invalid")
    if row["redeemed_by_tenant_id"] is not None:
        raise ValidationError("voucher_redeemed")
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.now(UTC):
        raise ValidationError("voucher_expired")
    return True


async def redeem_voucher(control_db, tenant_id: int, code: str) -> None:
    """Mark a voucher as redeemed by a tenant."""
    from datetime import UTC, datetime

    await control_db.execute(
        """
        UPDATE vouchers
        SET redeemed_by_tenant_id = ?, redeemed_at = ?
        WHERE code = ?
        """,
        (tenant_id, datetime.now(UTC).isoformat(), code),
    )
