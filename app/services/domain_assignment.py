"""Domain assignment business rules and persistence."""

import datetime

import orjson

from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError, ValidationError


async def _current_version_id(db: TenantDB) -> int:
    row = await db.fetchone(
        "SELECT id FROM wisp_versions WHERE status = 'in_progress' ORDER BY number DESC LIMIT 1"
    )
    if row is None:
        raise NotFoundError("No in-progress WISP version found")
    return row["id"]


async def _require_active_user_with_role(db: TenantDB, email: str, role: str) -> dict:
    row = await db.fetchone(
        "SELECT id, email, roles, status FROM users WHERE email = ?",
        (email,),
    )
    if row is None:
        raise NotFoundError(f"User {email} not found")
    if row["status"] != "active":
        raise ValidationError(f"User {email} is not active", code="user_inactive")
    roles = orjson.loads(row["roles"])
    if role not in roles:
        raise ValidationError(f"User {email} does not have the {role} role", code="missing_role")
    return dict(row)


async def assign_domain(
    db: TenantDB,
    *,
    actor_user_id: int,
    code: str,
    contributor_email: str,
    reviewer_email: str,
) -> dict:
    """Assign exactly one contributor and one reviewer to a domain."""
    version_id = await _current_version_id(db)
    domain = await db.fetchone(
        "SELECT id, code, name, status FROM domains WHERE code = ? AND wisp_version_id = ?",
        (code, version_id),
    )
    if domain is None:
        raise NotFoundError(f"Domain {code} not found")

    if domain["status"] not in ("pending_questions", "ready", "assigned"):
        raise ConflictError(
            f"Domain {code} cannot be reassigned while {domain['status']}",
            code="domain_not_reassignable",
        )

    contributor = await _require_active_user_with_role(db, contributor_email, "contributor")
    reviewer = await _require_active_user_with_role(db, reviewer_email, "reviewer")

    existing = await db.fetchone(
        "SELECT contributor_id, reviewer_id FROM domain_assignments WHERE domain_id = ?",
        (domain["id"],),
    )

    await db.execute("BEGIN IMMEDIATE")
    try:
        if existing is not None:
            await db.execute(
                "DELETE FROM domain_assignments WHERE domain_id = ?",
                (domain["id"],),
            )

        await db.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            """,
            (domain["id"], contributor["id"], reviewer["id"]),
        )

        if domain["status"] != "assigned":
            await db.execute(
                "UPDATE domains SET status = 'assigned' WHERE id = ?",
                (domain["id"],),
            )

        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "domain_id": domain["id"],
        "code": domain["code"],
        "contributor_id": contributor["id"],
        "contributor_email": contributor["email"],
        "reviewer_id": reviewer["id"],
        "reviewer_email": reviewer["email"],
        "assigned_at": datetime.datetime.utcnow().isoformat(),
    }
