"""User and role management services."""

import json

from app.db.tenant import TenantDB
from app.exceptions import NotFoundError
from app.services.notifications import notify


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
    await notify(
        db,
        user_id=target["id"],
        kind="roles_updated",
        payload={"roles": ", ".join(roles)},
        channel="both",
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
        "SELECT id, email FROM users WHERE email = ?",
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
            WHERE id IN ({placeholders}) AND status IN ('assigned', 'ready', 'in_progress')
            """,
            tuple(domain_ids),
        )

    await db.execute(
        "UPDATE users SET status = 'deactivated' WHERE id = ?",
        (user_id,),
    )
    await notify(
        db,
        user_id=user_id,
        kind="account_deactivated",
        payload={"email": target["email"]},
        channel="both",
    )
    await db.commit()
    return {"id": user_id, "email": target_email, "status": "deactivated"}


async def reactivate_user(
    db: TenantDB,
    *,
    actor_user_id: int,
    target_email: str,
) -> dict:
    """Reactivate a deactivated user."""
    target = await db.fetchone(
        "SELECT id, email FROM users WHERE email = ?",
        (target_email,),
    )
    if target is None:
        raise NotFoundError("User not found")
    await db.execute(
        "UPDATE users SET status = 'active' WHERE id = ?",
        (target["id"],),
    )
    await notify(
        db,
        user_id=target["id"],
        kind="account_reactivated",
        payload={"email": target["email"]},
        channel="both",
    )
    await db.commit()
    return {"id": target["id"], "email": target_email, "status": "active"}


async def delete_user(
    db: TenantDB,
    *,
    actor_user_id: int,
    target_email: str,
) -> None:
    """Permanently remove a user and clean up their assignments."""
    target = await db.fetchone(
        "SELECT id FROM users WHERE email = ?",
        (target_email,),
    )
    if target is None:
        raise NotFoundError("User not found")
    user_id = target["id"]

    assigned = await db.fetchall(
        "SELECT domain_id FROM domain_assignments WHERE contributor_id = ? OR reviewer_id = ?",
        (user_id, user_id),
    )
    domain_ids = {row["domain_id"] for row in assigned}

    await db.execute(
        "DELETE FROM domain_assignments WHERE contributor_id = ? OR reviewer_id = ?",
        (user_id, user_id),
    )
    if domain_ids:
        placeholders = ",".join("?" * len(domain_ids))
        statuses = ("'assigned'", "'ready'", "'in_progress'")
        status_list = ",".join(statuses)
        await db.execute(
            f"""
            UPDATE domains SET status = 'pending_questions'
            WHERE id IN ({placeholders})
            AND status IN ({status_list})
            """,
            tuple(domain_ids),
        )

    await db.execute("DELETE FROM invitations WHERE email = ?", (target_email,))
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
