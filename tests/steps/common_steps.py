"""Shared Gherkin step definitions across features."""

from pytest_bdd import given, parsers

from app.db.tenant import get_tenant_db


@given(parsers.parse('a provisioned tenant "{slug}"'), target_fixture="tenant_slug")
def given_provisioned_tenant(slug):
    """Set the tenant slug expected by the provisioned_tenant fixture."""
    return slug


@given(
    parsers.parse('an enrolled user "{email}" with password "{password}"'),
    target_fixture="enrolled_user",
)
async def given_enrolled_user(provisioned_tenant, data_dir, email, password):
    """Create a user in the tenant database with the given credentials."""
    from app.services.auth import create_user

    db = await get_tenant_db(data_dir, provisioned_tenant)
    try:
        user_id = await create_user(db, email, password, ["admin"])
        return {"id": user_id, "email": email, "password": password}
    finally:
        await db.close()
