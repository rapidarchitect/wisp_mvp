"""Test-only endpoints for frontend E2E support. Disabled outside test mode."""

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.auth import hash_password

router = APIRouter()


def _require_test_mode():
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/invitations")
async def list_invitations(request: Request, email: str | None = None) -> list[dict]:
    """Return invitations so E2E tests can extract activation tokens."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    if email:
        rows = await db.fetchall(
            "SELECT email, roles, token, expires_at, accepted_at FROM invitations WHERE email = ?",
            (email,),
        )
    else:
        rows = await db.fetchall(
            """
            SELECT email, roles, token, expires_at, accepted_at
            FROM invitations
            ORDER BY id DESC LIMIT 10
            """
        )
    return [dict(row) for row in rows]


@router.post("/users")
async def create_test_user(request: Request, payload: dict) -> dict:
    """Create a user directly for E2E seeding."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    await db.execute(
        """
        INSERT INTO users (
            email, password_hash, roles, status, totp_secret, totp_enrolled, failed_attempts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["email"],
            hash_password(payload["password"]),
            payload.get("roles", '["contributor"]'),
            payload.get("status", "active"),
            payload.get("totp_secret"),
            1 if payload.get("totp_enrolled", True) else 0,
            0,
        ),
    )
    await db.commit()
    return {"created": True}


@router.post("/reset-domain/{code}")
async def reset_domain(request: Request, code: str) -> dict:
    """Reset a single domain to assigned status and delete its answers."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    row = await db.fetchone("SELECT id FROM domains WHERE code = ?", (code,))
    if not row:
        raise HTTPException(status_code=404, detail="domain not found")
    domain_id = row["id"]
    await db.execute(
        "DELETE FROM answers WHERE question_id IN (SELECT id FROM questions WHERE domain_id = ?)",
        (domain_id,),
    )
    await db.execute("DELETE FROM compiled_answers WHERE domain_id = ?", (domain_id,))
    await db.execute(
        "UPDATE domains SET status = 'assigned' WHERE id = ?",
        (domain_id,),
    )
    await db.execute(
        "UPDATE wisp_versions SET status = 'in_progress', completed_at = NULL "
        "WHERE id = (SELECT wisp_version_id FROM domains WHERE id = ?)",
        (domain_id,),
    )
    await db.commit()
    return {"reset": True}


@router.post("/reset-all")
async def reset_all(request: Request) -> dict:
    """Reset the entire demo tenant to a known E2E baseline."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    await db.execute(
        "DELETE FROM followups WHERE answer_id IN (SELECT id FROM answers)"
    )
    await db.execute("DELETE FROM answers")
    await db.execute("DELETE FROM compiled_answers")
    await db.execute("DELETE FROM domain_assignments")
    await db.execute("UPDATE wisp_versions SET status = 'in_progress', completed_at = NULL")
    await db.execute("UPDATE domains SET status = 'pending_questions'")

    contributor = await db.fetchone(
        "SELECT id FROM users WHERE email = ?", ("contributor@demo.example.com",)
    )
    reviewer = await db.fetchone(
        "SELECT id FROM users WHERE email = ?", ("reviewer@demo.example.com",)
    )
    domain = await db.fetchone("SELECT id FROM domains WHERE code = ?", ("AC",))
    if contributor and reviewer and domain:
        await db.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            ON CONFLICT(domain_id) DO UPDATE SET
                contributor_id = excluded.contributor_id,
                reviewer_id = excluded.reviewer_id
            """,
            (domain["id"], contributor["id"], reviewer["id"]),
        )
        await db.execute(
            "UPDATE domains SET status = 'assigned' WHERE id = ?",
            (domain["id"],),
        )

    await db.commit()
    return {"reset": True}


@router.get("/domains")
async def list_all_domains(request: Request) -> list[dict]:
    """Return all domain codes in the current tenant version for E2E helpers."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    rows = await db.fetchall(
        """
        SELECT d.code, d.status
        FROM domains d
        WHERE d.wisp_version_id = (SELECT id FROM wisp_versions ORDER BY number DESC LIMIT 1)
        ORDER BY d.code
        """
    )
    return [dict(row) for row in rows]
