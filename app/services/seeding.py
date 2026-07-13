"""Domain seeding orchestration."""

from app.crews.seeder_crew import SeederCrew
from app.db.tenant import TenantDB
from app.services.domain import get_domains_for_version


async def seed_all_domains(
    db: TenantDB,
    *,
    version_id: int,
    llm=None,
) -> dict:
    """Fan out seeding across all 14 domains for a WISP version."""
    domains = await get_domains_for_version(db, version_id=version_id)
    results = []
    for domain in domains:
        crew = SeederCrew(
            db,
            domain_id=domain["id"],
            domain_code=domain["code"],
            domain_name=domain["name"],
            llm=llm,
        )
        result = await crew.seed_domain()
        results.append(result)

    return {
        "version_id": version_id,
        "domains": len(results),
        "results": results,
    }


async def retry_domain_seed(
    db: TenantDB,
    *,
    domain_id: int,
    llm=None,
) -> dict:
    """Retry seeding for a single domain that is in a pending state."""
    domain = await db.fetchone(
        "SELECT id, code, name, wisp_version_id, status FROM domains WHERE id = ?",
        (domain_id,),
    )
    if domain is None:
        raise ValueError(f"Domain {domain_id} not found")
    if domain["status"] != "pending_questions":
        raise ValueError(f"Domain {domain_id} is not in pending_questions state")

    crew = SeederCrew(
        db,
        domain_id=domain["id"],
        domain_code=domain["code"],
        domain_name=domain["name"],
        llm=llm,
    )
    return await crew.seed_domain()
