"""Review workflow service (Task 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.crews.revision_crew import RevisionCrew
from app.db.tenant import TenantDB
from app.exceptions import (
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
)
from app.services import compilation as compilation_service
from app.services.audit import audit
from app.services.notifications import notify


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def approve_domain(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
) -> dict:
    """Approve a domain that is currently in review."""
    domain, compiled = await _resolve_domain_with_compiled(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError(
            "domain not assigned to this reviewer",
            code="forbidden",
        )
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    await db.execute(
        "UPDATE compiled_answers SET approved_at = ? WHERE id = ?",
        (_now(), compiled["id"]),
    )
    await db.execute(
        "UPDATE domains SET status = 'approved' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_approved",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["contributor_id"],
        kind="domain_approved",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )

    wisp_complete = await _maybe_complete_version(db, version_id=domain["wisp_version_id"])
    if wisp_complete:
        admin = await _find_admin(db)
        if admin is not None:
            await notify(
                db,
                user_id=admin["id"],
                kind="wisp_complete",
                payload={},
                channel="in_app",
            )
        await audit(
            db,
            actor_user_id=reviewer_id,
            event_type="wisp_completed",
            subject=f"version:{domain['wisp_version_id']}",
            detail="",
            commit=False,
        )

    await db.commit()

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "approved",
        "self_review": domain["contributor_id"] == reviewer_id,
        "wisp_complete": wisp_complete,
    }


async def revise_and_approve(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
    revision_prompt: str,
    llm: Any | None = None,
) -> dict:
    """Revise the compiled narrative and immediately approve the domain."""
    domain, compiled = await _resolve_domain_with_compiled(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError(
            "domain not assigned to this reviewer",
            code="forbidden",
        )
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    contributor_id = domain["contributor_id"]
    questions = await compilation_service.load_answered_questions(
        db, domain_id=domain["id"], contributor_id=contributor_id
    )
    conversation = [
        {
            "question": q["text"],
            "answer": "skipped" if q["answer"]["skipped"] else q["answer"]["value"],
            "followups": [
                {
                    "text": f["text"],
                    "response": f.get("response_text") or "",
                }
                for f in q["answer"].get("followups", [])
            ],
        }
        for q in questions
    ]

    crew = RevisionCrew(
        db,
        domain_code=code,
        domain_name=domain["name"],
        current_narrative=compiled["narrative_text"],
        conversation=conversation,
        llm=llm,
    )
    try:
        new_narrative = await crew.revise(revision_prompt)
    except Exception as exc:
        raise ExternalServiceError(
            "revision failed; please retry",
            code="llm_unavailable",
        ) from exc

    await db.execute(
        """
        UPDATE compiled_answers
        SET narrative_text = ?, revised_by_reviewer_id = ?
        WHERE id = ?
        """,
        (new_narrative, reviewer_id, compiled["id"]),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_revised",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )

    # Reuse approval state transition and audit after persisting the revision,
    # but send the distinct revised-and-approved notification.
    approve_result = await approve_domain(db, reviewer_id=reviewer_id, code=code)
    await notify(
        db,
        user_id=domain["contributor_id"],
        kind="domain_revised_and_approved",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )
    return approve_result


async def defer_domain(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
) -> dict:
    """Return a domain to the contributor for more information."""
    domain = await _resolve_domain(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError(
            "domain not assigned to this reviewer",
            code="forbidden",
        )
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    await db.execute(
        "UPDATE domains SET status = 'in_progress' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_deferred",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["contributor_id"],
        kind="domain_deferred",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )
    await db.commit()

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "in_progress",
    }


async def _resolve_domain(db: TenantDB, code: str) -> dict[str, Any]:
    version = await db.fetchone(
        "SELECT id FROM wisp_versions WHERE status = 'in_progress' ORDER BY number DESC LIMIT 1"
    )
    if version is None:
        raise NotFoundError("no in-progress version")

    domain = await db.fetchone(
        """
        SELECT d.*, a.contributor_id, a.reviewer_id
        FROM domains d
        LEFT JOIN domain_assignments a ON a.domain_id = d.id
        WHERE d.wisp_version_id = ? AND d.code = ?
        """,
        (version["id"], code),
    )
    if domain is None:
        raise NotFoundError("domain not found")
    return dict(domain)


async def _resolve_domain_with_compiled(
    db: TenantDB, code: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    domain = await _resolve_domain(db, code)
    compiled = await db.fetchone(
        "SELECT * FROM compiled_answers WHERE domain_id = ?",
        (domain["id"],),
    )
    if compiled is None:
        raise ConflictError(
            "domain has no compiled answer",
            code="missing_compiled_answer",
        )
    return domain, dict(compiled)


async def _maybe_complete_version(db: TenantDB, *, version_id: int) -> bool:
    total = await db.fetchone(
        "SELECT COUNT(*) AS count FROM domains WHERE wisp_version_id = ?",
        (version_id,),
    )
    approved = await db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM domains
        WHERE wisp_version_id = ? AND status = 'approved'
        """,
        (version_id,),
    )
    if approved["count"] == total["count"]:
        await db.execute(
            "UPDATE wisp_versions SET status = 'complete', completed_at = ? WHERE id = ?",
            (_now(), version_id),
        )
        return True
    return False


async def _find_admin(db: TenantDB) -> dict[str, Any] | None:
    import orjson

    rows = await db.fetchall("SELECT id, roles FROM users WHERE status = 'active'")
    for row in rows:
        roles = orjson.loads(row["roles"])
        if "admin" in roles:
            return dict(row)
    return None
