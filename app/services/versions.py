"""WISP version lifecycle service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def get_version(db: TenantDB, version_id: int) -> dict[str, Any]:
    """Return a single version by id."""
    row = await db.fetchone(
        """
        SELECT id, tenant_id, number, status, created_at, completed_at
        FROM wisp_versions
        WHERE id = ?
        """,
        (version_id,),
    )
    if row is None:
        raise NotFoundError(f"version {version_id} not found")
    return dict(row)


async def get_current_version(db: TenantDB, *, tenant_id: int) -> dict[str, Any]:
    """Return the most recently created version for a tenant."""
    row = await db.fetchone(
        """
        SELECT id, tenant_id, number, status, created_at, completed_at
        FROM wisp_versions
        WHERE tenant_id = ?
        ORDER BY number DESC
        LIMIT 1
        """,
        (tenant_id,),
    )
    if row is None:
        raise NotFoundError("no version found")
    return dict(row)


async def list_versions(db: TenantDB, *, tenant_id: int) -> list[dict[str, Any]]:
    """List all versions for a tenant, newest first."""
    rows = await db.fetchall(
        """
        SELECT id, tenant_id, number, status, created_at, completed_at
        FROM wisp_versions
        WHERE tenant_id = ?
        ORDER BY number DESC
        """,
        (tenant_id,),
    )
    return [dict(row) for row in rows]


async def start_new_version(
    db: TenantDB,
    *,
    tenant_id: int,
    created_by_user_id: int,
) -> dict[str, Any]:
    """Create a new WISP version from the approved baseline of the previous version.

    Enforces only one in-progress version per tenant (C-14).
    """
    in_progress = await db.fetchone(
        "SELECT id FROM wisp_versions WHERE tenant_id = ? AND status = 'in_progress'",
        (tenant_id,),
    )
    if in_progress is not None:
        raise ConflictError(
            "a version is already in progress",
            code="version_in_progress",
        )

    previous = await db.fetchone(
        "SELECT id, number FROM wisp_versions WHERE tenant_id = ? ORDER BY number DESC LIMIT 1",
        (tenant_id,),
    )
    if previous is None:
        raise NotFoundError("no previous version to clone")

    previous_id = previous["id"]
    new_number = previous["number"] + 1

    cursor = await db.execute(
        """
        INSERT INTO wisp_versions (tenant_id, number, status, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (tenant_id, new_number, "in_progress", _now()),
    )
    new_version_id = cursor.lastrowid

    # Clone approved domains with their compiled answers and assignments.
    await db.execute(
        """
        INSERT INTO domains (code, name, wisp_version_id, status)
        SELECT code, name, ?, 'assigned'
        FROM domains
        WHERE wisp_version_id = ?
        """,
        (new_version_id, previous_id),
    )

    rows = await db.fetchall(
        """
        SELECT d_new.id AS new_domain_id, d_old.id AS old_domain_id
        FROM domains d_new
        JOIN domains d_old ON d_old.code = d_new.code AND d_old.wisp_version_id = ?
        WHERE d_new.wisp_version_id = ?
        """,
        (previous_id, new_version_id),
    )

    for row in rows:
        old_domain_id = row["old_domain_id"]
        new_domain_id = row["new_domain_id"]

        old_domain = await db.fetchone("SELECT status FROM domains WHERE id = ?", (old_domain_id,))
        if old_domain is None:
            continue

        if old_domain["status"] == "approved":
            compiled = await db.fetchone(
                "SELECT narrative_text FROM compiled_answers WHERE domain_id = ?",
                (old_domain_id,),
            )
            if compiled is not None:
                await db.execute(
                    """
                    INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at)
                    VALUES (?, ?, ?)
                    """,
                    (new_domain_id, compiled["narrative_text"], _now()),
                )

            assignments = await db.fetchall(
                """
                SELECT contributor_id, reviewer_id
                FROM domain_assignments
                WHERE domain_id = ?
                """,
                (old_domain_id,),
            )
            for assignment in assignments:
                await db.execute(
                    """
                    INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                    VALUES (?, ?, ?)
                    """,
                    (
                        new_domain_id,
                        assignment["contributor_id"],
                        assignment["reviewer_id"],
                    ),
                )

    await db.commit()
    return {
        "version_id": new_version_id,
        "tenant_id": tenant_id,
        "number": new_number,
        "status": "in_progress",
        "previous_version_id": previous_id,
    }
