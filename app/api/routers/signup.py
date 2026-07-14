"""Signup API router (Task 06)."""

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.models.signup import SignupRequest, WebhookRequest
from app.services.payment import FakeStripeClient, get_default_stripe_client
from app.services.signup import confirm_payment, process_signup

router = APIRouter()


def _control_db_path(request: Request) -> str:
    return str(request.app.state.control_db_path)


def _data_dir(request: Request) -> str:
    return str(request.app.state.data_dir)


def _stripe_client(request: Request) -> FakeStripeClient:
    client = getattr(request.app.state, "stripe_client", None)
    return client if client is not None else get_default_stripe_client()


@router.post("")
async def signup(request: Request, payload: SignupRequest) -> dict:
    """Begin signup: validate, create tenant record, initiate payment."""
    slug = request.state.tenant_slug
    if not slug:
        raise HTTPException(status_code=400, detail="workspace_required")

    result = await process_signup(
        control_db_path=_control_db_path(request),
        data_dir=_data_dir(request),
        slug=slug,
        company_name=payload.company_name,
        address=payload.address,
        workspace_email=payload.workspace_email,
        funding=payload.funding,
        voucher_code=payload.voucher_code,
        vitals=payload.vitals.model_dump(),
        stripe_client=_stripe_client(request),
    )
    return result


@router.post("/webhook")
async def signup_webhook(request: Request, payload: WebhookRequest) -> dict:
    """Stripe webhook confirming payment and triggering provisioning."""
    result = await confirm_payment(
        control_db_path=_control_db_path(request),
        data_dir=_data_dir(request),
        checkout_id=payload.checkout_id,
        stripe_client=_stripe_client(request),
    )
    return result


@router.post("/test-confirm-card")
async def test_confirm_card(request: Request, payload: WebhookRequest) -> dict:
    """Test-only endpoint to complete a fake card checkout and provision the tenant.

    Disabled in production. Used by frontend E2E tests to simulate Stripe success.
    """
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="not_found")
    result = await confirm_payment(
        control_db_path=_control_db_path(request),
        data_dir=_data_dir(request),
        checkout_id=payload.checkout_id,
        stripe_client=_stripe_client(request),
    )
    return result
