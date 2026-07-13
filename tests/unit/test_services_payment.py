"""Unit tests for payment abstraction."""

import pytest

from app.services.payment import FakeStripeClient, PaymentError


async def test_fake_stripe_create_checkout_succeeds():
    client = FakeStripeClient("succeed")
    session = await client.create_checkout_session(amount_cents=4900, tenant_slug="acme")

    assert session.id.startswith("cs_test_acme_")
    assert session.status == "open"
    assert session.url is not None


async def test_fake_stripe_create_checkout_declines():
    client = FakeStripeClient("decline")
    with pytest.raises(PaymentError):
        await client.create_checkout_session(amount_cents=4900, tenant_slug="acme")


async def test_fake_stripe_get_checkout_succeeds():
    client = FakeStripeClient("succeed")
    session = await client.get_checkout_session("cs_test_123")
    assert session.status == "complete"


async def test_fake_stripe_get_checkout_declines():
    client = FakeStripeClient("decline")
    with pytest.raises(PaymentError):
        await client.get_checkout_session("cs_test_123")
