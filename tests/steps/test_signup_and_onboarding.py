"""pytest-bdd step definitions for the signup and onboarding feature."""

import sqlite3

from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/signup-and-onboarding.feature",
    "Card signup provisions workspace (SIGN-01)",
)
def test_card_signup_provisions_workspace_sign01():
    pass


@scenario(
    "../../features/signup-and-onboarding.feature",
    "Voucher skips card payment (SIGN-02)",
)
def test_voucher_skips_card_payment_sign02():
    pass


@scenario(
    "../../features/signup-and-onboarding.feature",
    "Declined card leaves no workspace (SIGN-03)",
)
def test_declined_card_leaves_no_workspace_sign03():
    pass


@scenario(
    "../../features/signup-and-onboarding.feature",
    "Workspace address must be unique (SIGN-04)",
)
def test_workspace_address_must_be_unique_sign04():
    pass


@scenario(
    "../../features/signup-and-onboarding.feature",
    "Corporate vitals validation (SIGN-05)",
)
def test_corporate_vitals_validation_sign05():
    pass


def _control_db_path(data_dir):
    return data_dir / "control.db"


def _tenant_db_path(data_dir, slug):
    return data_dir / "tenants" / f"{slug}.db"


@given(parsers.parse('the visitor uses the "{slug}" workspace address'))
def given_visitor_uses_workspace(context, slug):
    """Set the desired workspace slug for the signup."""
    context["slug"] = slug


@given("the visitor provides valid corporate vitals")
def given_visitor_provides_valid_vitals(context):
    """Store a complete set of valid corporate vitals."""
    context["vitals"] = {
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


@given(parsers.re(r'the visitor provides corporate vitals with (?P<field>[^\s]+) "(?P<value>.*)"'))
def given_visitor_provides_vitals_with_field(context, field, value):
    """Store valid vitals with one field overridden."""
    context["vitals"] = {
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
    context["vitals"][field] = value


@given(parsers.parse('the visitor chooses "{funding}" payment'))
def given_visitor_chooses_payment(context, funding):
    """Set the funding method (card or voucher)."""
    context["funding"] = funding
    context["voucher_code"] = None


@given(parsers.parse('the visitor chooses "{funding}" payment with code "{code}"'))
def given_visitor_chooses_payment_with_code(context, funding, code):
    """Set the funding method and voucher code."""
    context["funding"] = funding
    context["voucher_code"] = code


@given(parsers.parse('a valid voucher "{code}"'))
def given_valid_voucher(control_db_path, code):
    """Insert a redeemable voucher into the control database."""
    from datetime import UTC, datetime, timedelta

    conn = sqlite3.connect(control_db_path)
    try:
        conn.execute(
            """
            INSERT INTO vouchers (code, issued_to, redeemed_by_tenant_id, redeemed_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                code,
                "test-issuer",
                None,
                None,
                (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('a tenant already exists with slug "{slug}"'))
def given_tenant_already_exists(control_db_path, slug):
    """Seed a tenant with the given slug to test uniqueness."""
    conn = sqlite3.connect(control_db_path)
    try:
        conn.execute(
            "INSERT INTO tenants (slug, company_name, address, status) VALUES (?, ?, ?, ?)",
            (slug, "Existing Firm", "123 Main St", "active"),
        )
        conn.commit()
    finally:
        conn.close()


@when("the visitor submits signup")
def when_visitor_submits_signup(client, context, data_dir):
    """POST /signup with the collected payload."""
    payload = {
        "company_name": "Palmetto Tax",
        "address": "123 Main St",
        "workspace_email": "admin@palmetto.app.wisp.llc",
        "funding": context["funding"],
        "voucher_code": context.get("voucher_code"),
        "vitals": context["vitals"],
    }
    context["response"] = client.post(
        "/signup",
        json=payload,
        headers={"X-Workspace-Slug": context["slug"]},
    )


@then("a Stripe Checkout session is created")
def then_stripe_checkout_session_created(context):
    """Assert the signup response contains a checkout id."""
    response = context["response"]
    assert response.status_code == 200
    data = response.json()
    assert "checkout_id" in data
    context["checkout_id"] = data["checkout_id"]


@when("the payment is confirmed")
def when_payment_is_confirmed(client, context):
    """POST the Stripe success webhook to confirm payment and provision."""
    context["response"] = client.post(
        "/signup/webhook",
        json={"event": "checkout.session.completed", "checkout_id": context["checkout_id"]},
    )


@then("a tenant workspace is provisioned")
def then_tenant_workspace_provisioned(control_db_path, data_dir, context):
    """Verify the tenant is active and its SQLite file exists."""
    slug = context["slug"]
    conn = sqlite3.connect(control_db_path)
    try:
        cur = conn.execute(
            "SELECT status FROM tenants WHERE slug = ?",
            (slug,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "active"
    finally:
        conn.close()
    assert _tenant_db_path(data_dir, slug).exists()


@then("an initial WISP version exists")
def then_initial_wisp_version_exists(data_dir, context):
    """Verify version 1 exists in the tenant database."""
    path = _tenant_db_path(data_dir, context["slug"])
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT number, status FROM wisp_versions WHERE number = 1")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "in_progress"
    finally:
        conn.close()


@then("14 domains exist")
def then_14_domains_exist(data_dir, context):
    """Verify the tenant database contains all 14 security domains."""
    path = _tenant_db_path(data_dir, context["slug"])
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM domains")
        assert cur.fetchone()[0] == 14
    finally:
        conn.close()


@then("no Stripe Checkout session is created")
def then_no_stripe_checkout_session_created(context):
    """Assert the signup response does not include a checkout id."""
    response = context["response"]
    assert response.status_code == 200
    assert "checkout_id" not in response.json()


@then("the voucher is marked as redeemed")
def then_voucher_marked_redeemed(control_db_path, context):
    """Verify the voucher row records the redeeming tenant."""
    code = context["voucher_code"]
    conn = sqlite3.connect(control_db_path)
    try:
        cur = conn.execute(
            "SELECT redeemed_by_tenant_id FROM vouchers WHERE code = ?",
            (code,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] is not None
    finally:
        conn.close()


@when("Stripe declines the card")
def when_stripe_declines_card(client, context):
    """Simulate Stripe declining the card via the webhook endpoint."""
    from app.services.payment import FakeStripeClient

    checkout_id = context["response"].json()["checkout_id"]
    client.app.state.stripe_client = FakeStripeClient("decline")
    context["response"] = client.post(
        "/signup/webhook",
        json={"event": "checkout.session.completed", "checkout_id": checkout_id},
    )


@then("no tenant workspace is provisioned")
def then_no_tenant_workspace_provisioned(control_db_path, data_dir, context):
    """Verify the tenant is not active and no tenant DB file exists."""
    slug = context["slug"]
    conn = sqlite3.connect(control_db_path)
    try:
        cur = conn.execute(
            "SELECT status FROM tenants WHERE slug = ?",
            (slug,),
        )
        row = cur.fetchone()
        if row is not None:
            assert row[0] != "active"
    finally:
        conn.close()
    assert not _tenant_db_path(data_dir, slug).exists()


@then("no tenant DB file is created")
def then_no_tenant_db_file_created(data_dir, context):
    """Verify the tenant SQLite file was never created."""
    assert not _tenant_db_path(data_dir, context["slug"]).exists()


@then(parsers.parse('the signup is rejected with "{code}"'))
def then_signup_rejected(context, code):
    """Assert the signup response status and error code."""
    response = context["response"]
    assert response.status_code in (409, 422)
    assert response.json()["error"]["code"] == code
