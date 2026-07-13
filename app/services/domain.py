"""Domain query and state helpers."""

from app.db.tenant import TenantDB


async def get_domains_for_version(db: TenantDB, *, version_id: int) -> list[dict]:
    """Return all domains for a WISP version."""
    rows = await db.fetchall(
        "SELECT id, code, name, status FROM domains WHERE wisp_version_id = ?",
        (version_id,),
    )
    return [dict(row) for row in rows]


async def get_questions_for_domain(db: TenantDB, *, domain_id: int) -> list[dict]:
    """Return all questions for a domain."""
    rows = await db.fetchall(
        """
        SELECT id, text, answer_type, origin, enabled, position
        FROM questions
        WHERE domain_id = ?
        """,
        (domain_id,),
    )
    return [dict(row) for row in rows]
