"""User and role management services."""

import json

from app.db.tenant import TenantDB
from app.exceptions import NotFoundError


async def list_users(db: TenantDB) -> list[dict]:
    """Return all users with their roles and status."""
    rows = await db.fetchall("SELECT id, email, roles, status FROM users ORDER BY email")
    return [
        {
            "id": row["id"],
            "email": row["email"],
            "roles": json.loads(row["roles"]),
            "status": row["status"],
        }
        for row in rows
    ]


async def set_roles(
    db: TenantDB,
    *,
    actor_user_id: int,
    target_email: str,
    roles: list[str],
) -> dict:
    """Replace a user's roles."""
    target = await db.fetchone(
        "SELECT id FROM users WHERE email = ?",
        (target_email,),
    )
    if target is None:
        raise NotFoundError("User not found")

    await db.execute(
        "UPDATE users SET roles = ? WHERE id = ?",
        (json.dumps(roles), target["id"]),
    )
    await db.commit()
    return {"id": target["id"], "email": target_email, "roles": roles}


async def deactivate_user(
    db: TenantDB,
    *,
    actor_user_id: int,
    target_email: str,
) -> dict:
    """Deactivate a user and unassign their domains."""
    target = await db.fetchone(
        "SELECT id FROM users WHERE email = ?",
        (target_email,),
    )
    if target is None:
        raise NotFoundError("User not found")

    user_id = target["id"]

    # Find domains where the user is contributor or reviewer.
    assigned = await db.fetchall(
        """
        SELECT domain_id, contributor_id, reviewer_id FROM domain_assignments
        WHERE contributor_id = ? OR reviewer_id = ?
        """,
        (user_id, user_id),
    )
    domain_ids = {row["domain_id"] for row in assigned}

    await db.execute(
        "DELETE FROM domain_assignments WHERE contributor_id = ? OR reviewer_id = ?",
        (user_id, user_id),
    )
    if domain_ids:
        placeholders = ",".join("?" * len(domain_ids))
        await db.execute(
            f"""
            UPDATE domains SET status = 'pending_questions'
            WHERE id IN ({placeholders}) AND status = 'assigned'
            """,
            tuple(domain_ids),
        )

    await db.execute(
        "UPDATE users SET status = 'deactivated' WHERE id = ?",
        (user_id,),
    )
    await db.commit()
    return {"id": user_id, "email": target_email, "status": "deactivated"}
