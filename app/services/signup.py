"""Signup orchestration: validate, persist, collect payment, provision."""

from pathlib import Path

from app.db.control import get_control_db
from app.exceptions import ConflictError, ValidationError
from app.services.payment import (
    FakeStripeClient,
    get_default_stripe_client,
    redeem_voucher,
    validate_voucher,
)
from app.services.provisioning import provision_tenant


async def process_signup(
    *,
    control_db_path: str | Path,
    data_dir: str | Path,
    slug: str,
    company_name: str,
    address: str,
    workspace_email: str,
    funding: str,
    voucher_code: str | None,
    vitals: dict,
    stripe_client: FakeStripeClient | None = None,
) -> dict:
    """Validate signup input, create tenant/subscription records, return next step.

    Returns:
        {"checkout_id": str} for card payments.
        {"provisioned": True} for voucher payments.
    """
    _validate_vitals(vitals)

    control_db = await get_control_db(control_db_path)
    try:
        existing = await control_db.execute(
            "SELECT id FROM tenants WHERE slug = ?",
            (slug,),
        )
        if await existing.fetchone() is not None:
            raise ConflictError("Workspace address is already taken", code="slug_taken")

        cursor = await control_db.execute(
            """
            INSERT INTO tenants (slug, company_name, address, status)
            VALUES (?, ?, ?, ?)
            """,
            (slug, company_name, address, "provisioning"),
        )
        tenant_id = cursor.lastrowid

        if funding == "voucher":
            if not voucher_code:
                raise ValidationError("voucher_required")
            await validate_voucher(control_db, voucher_code)
            await control_db.execute(
                """
                INSERT INTO subscriptions (tenant_id, tier, funding, voucher_code, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_id, "standard", "voucher", voucher_code, "active"),
            )
            await redeem_voucher(control_db, tenant_id, voucher_code)
            await control_db.execute(
                "UPDATE tenants SET status = ? WHERE id = ?",
                ("active", tenant_id),
            )
            await control_db.commit()
            await provision_tenant(
                control_db,
                tenant_id=tenant_id,
                slug=slug,
                data_dir=data_dir,
            )
            return {"provisioned": True}

        # funding == "card"
        client = stripe_client or get_default_stripe_client()
        try:
            session = await client.create_checkout_session(
                amount_cents=4900,
                tenant_slug=slug,
            )
        except Exception:
            await control_db.execute(
                "DELETE FROM tenants WHERE id = ?",
                (tenant_id,),
            )
            await control_db.commit()
            raise

        await control_db.execute(
            """
            INSERT INTO subscriptions (tenant_id, tier, funding, stripe_checkout_id, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tenant_id, "standard", "card", session.id, "active"),
        )
        await control_db.commit()
        return {"checkout_id": session.id}
    finally:
        await control_db.close()


async def confirm_payment(
    *,
    control_db_path: str | Path,
    data_dir: str | Path,
    checkout_id: str,
    stripe_client: FakeStripeClient | None = None,
) -> dict:
    """Confirm a checkout session, provision the tenant, or roll back on failure."""
    control_db = await get_control_db(control_db_path)
    try:
        row = await control_db.execute(
            """
            SELECT s.tenant_id, t.slug
            FROM subscriptions s
            JOIN tenants t ON t.id = s.tenant_id
            WHERE s.stripe_checkout_id = ?
            """,
            (checkout_id,),
        )
        subscription = await row.fetchone()
        if subscription is None:
            raise ValidationError("checkout_not_found")

        client = stripe_client or get_default_stripe_client()
        try:
            await client.get_checkout_session(checkout_id)
        except Exception:
            await control_db.execute(
                "DELETE FROM tenants WHERE id = ?",
                (subscription["tenant_id"],),
            )
            await control_db.commit()
            return {"provisioned": False}

        await control_db.execute(
            "UPDATE tenants SET status = ? WHERE id = ?",
            ("active", subscription["tenant_id"]),
        )
        await control_db.commit()
        await provision_tenant(
            control_db,
            tenant_id=subscription["tenant_id"],
            slug=subscription["slug"],
            data_dir=data_dir,
        )
        return {"provisioned": True}
    finally:
        await control_db.close()


def _validate_vitals(vitals: dict) -> None:
    """Enforce presence of required corporate vitals fields."""
    required = {
        "employee_range",
        "clients_per_year_range",
        "primary_software",
        "deployment_type",
        "coordinator_name",
        "coordinator_title",
    }
    missing = [f for f in required if not str(vitals.get(f, "")).strip()]
    if missing:
        raise ValidationError("Corporate vitals are incomplete", code="vitals_invalid")
