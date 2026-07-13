"""Unit tests for tenant provisioning."""

from app.db.tenant import init_tenant_db
from app.services.provisioning import create_14_domains, create_initial_version


async def test_create_initial_version(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    version_id = await create_initial_version(tenant_db, tenant_id=1)

    row = await tenant_db.fetchone(
        "SELECT number, status FROM wisp_versions WHERE id = ?",
        (version_id,),
    )
    assert row["number"] == 1
    assert row["status"] == "in_progress"
    await tenant_db.close()


async def test_create_14_domains(tmp_path):
    tenant_db = await init_tenant_db(tmp_path, "acme")
    version_id = await create_initial_version(tenant_db, tenant_id=1)
    await create_14_domains(tenant_db, version_id=version_id)
    await tenant_db.commit()

    row = await tenant_db.fetchone("SELECT COUNT(*) AS count FROM domains")
    assert row["count"] == 14

    codes = {r["code"] for r in await tenant_db.fetchall("SELECT code FROM domains")}
    assert codes == {
        "AC",
        "PE",
        "RA",
        "CA",
        "SC",
        "SI",
        "AT",
        "AU",
        "CM",
        "IA",
        "IR",
        "MA",
        "MP",
        "PS",
    }
    await tenant_db.close()
