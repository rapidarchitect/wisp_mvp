"""Tenant provisioning services: create DB, version, and 14 domains."""

from pathlib import Path

from app.db.tenant import init_tenant_db

_DOMAINS = [
    ("AC", "Access Control"),
    ("PE", "Personnel"),
    ("RA", "Risk Assessment"),
    ("CA", "Contingency Planning"),
    ("SC", "System and Communications Protection"),
    ("SI", "System and Information Integrity"),
    ("AT", "Awareness and Training"),
    ("AU", "Audit"),
    ("CM", "Configuration Management"),
    ("IA", "Identification and Authentication"),
    ("IR", "Incident Response"),
    ("MA", "Maintenance"),
    ("MP", "Media Protection"),
    ("PS", "Physical and Environmental Protection"),
]


async def provision_tenant(
    control_db,
    *,
    tenant_id: int,
    slug: str,
    data_dir: str | Path,
) -> None:
    """Create the tenant SQLite file, schema, version 1, and 14 domains."""
    tenant_db = await init_tenant_db(data_dir, slug)
    try:
        version_id = await create_initial_version(tenant_db, tenant_id=tenant_id)
        await create_14_domains(tenant_db, version_id=version_id)
        await tenant_db.commit()
    finally:
        await tenant_db.close()


async def create_initial_version(tenant_db, *, tenant_id: int) -> int:
    """Create WISP version 1 in the tenant DB and return its id."""
    cursor = await tenant_db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (tenant_id, 1, "in_progress"),
    )
    return cursor.lastrowid


async def create_14_domains(tenant_db, *, version_id: int) -> None:
    """Insert the 14 NIST-style security domains for a WISP version."""
    await tenant_db.executemany(
        "INSERT INTO domains (code, name, wisp_version_id) VALUES (?, ?, ?)",
        [(code, name, version_id) for code, name in _DOMAINS],
    )
