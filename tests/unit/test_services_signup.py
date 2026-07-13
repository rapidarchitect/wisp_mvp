"""Unit tests for signup orchestration."""

import pytest

from app.exceptions import ConflictError, ValidationError
from app.services.payment import FakeStripeClient
from app.services.signup import confirm_payment, process_signup


@pytest.fixture
def _valid_vitals():
    return {
        "employee_range": "1-10",
        "clients_per_year_range": "100-500",
        "primary_software": "QuickBooks Online",
        "deployment_type": "cloud",
        "has_efin": True,
        "it_support_provider": "Internal IT",
        "remote_access": True,
        "paper_files": False,
        "sensitive_data_types": ["ssn", "tax_records"],
        "coordinator_name": "Jane Doe",
        "coordinator_title": "Office Manager",
    }


@pytest.fixture
def _signup_kwargs(tmp_path, _valid_vitals):
    control_db_path = tmp_path / "control.db"
    data_dir = tmp_path
    return {
        "control_db_path": control_db_path,
        "data_dir": data_dir,
        "slug": "palmetto",
        "company_name": "Palmetto Tax",
        "address": "123 Main St",
        "workspace_email": "admin@palmetto.app.wisp.llc",
        "funding": "card",
        "voucher_code": None,
        "vitals": _valid_vitals,
    }


async def test_process_signup_card_returns_checkout_id(_signup_kwargs):
    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])

    result = await process_signup(**_signup_kwargs)

    assert "checkout_id" in result
    assert result["checkout_id"].startswith("cs_test_palmetto_")


async def test_process_signup_voucher_provisions_tenant(_signup_kwargs):
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])
    conn = sqlite3.connect(_signup_kwargs["control_db_path"])
    try:
        conn.execute(
            "INSERT INTO vouchers (code, issued_to, expires_at) VALUES (?, ?, ?)",
            ("WISP-UNIT-01", "test", (datetime.now(UTC) + timedelta(days=7)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    _signup_kwargs["funding"] = "voucher"
    _signup_kwargs["voucher_code"] = "WISP-UNIT-01"

    result = await process_signup(**_signup_kwargs)

    assert result == {"provisioned": True}
    tenant_db = _signup_kwargs["data_dir"] / "tenants" / "palmetto.db"
    assert tenant_db.exists()


async def test_process_signup_duplicate_slug_raises_slug_taken(_signup_kwargs):
    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])
    await process_signup(**_signup_kwargs)

    with pytest.raises(ConflictError) as exc_info:
        await process_signup(**_signup_kwargs)

    assert exc_info.value.code == "slug_taken"


async def test_process_signup_invalid_vitals_raises_vitals_invalid(_signup_kwargs):
    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])
    _signup_kwargs["vitals"]["coordinator_name"] = ""

    with pytest.raises(ValidationError) as exc_info:
        await process_signup(**_signup_kwargs)

    assert exc_info.value.code == "vitals_invalid"


async def test_confirm_payment_provisions_tenant(_signup_kwargs):
    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])
    signup_result = await process_signup(**_signup_kwargs)

    result = await confirm_payment(
        control_db_path=_signup_kwargs["control_db_path"],
        data_dir=_signup_kwargs["data_dir"],
        checkout_id=signup_result["checkout_id"],
    )

    assert result == {"provisioned": True}
    tenant_db = _signup_kwargs["data_dir"] / "tenants" / "palmetto.db"
    assert tenant_db.exists()


async def test_confirm_payment_declined_cleans_up(_signup_kwargs):
    from app.db.control import init_control_db

    await init_control_db(_signup_kwargs["control_db_path"])
    signup_result = await process_signup(
        **_signup_kwargs,
        stripe_client=FakeStripeClient("succeed"),
    )

    result = await confirm_payment(
        control_db_path=_signup_kwargs["control_db_path"],
        data_dir=_signup_kwargs["data_dir"],
        checkout_id=signup_result["checkout_id"],
        stripe_client=FakeStripeClient("decline"),
    )

    assert result == {"provisioned": False}
    tenant_db = _signup_kwargs["data_dir"] / "tenants" / "palmetto.db"
    assert not tenant_db.exists()
