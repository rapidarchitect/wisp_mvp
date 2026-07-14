"""Compilation and submission service (Task 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.crews.compiler_crew import CompilerCrew
from app.db.tenant import TenantDB
from app.exceptions import (
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
)
from app.services import followups as followups_service
from app.services.answers import get_domain_progress
from app.services.audit import audit
from app.services.notifications import notify


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def compile_domain(
    db: TenantDB,
    *,
    contributor_id: int,
    code: str,
    llm: Any | None = None,
) -> dict:
    """Compile a domain narrative if all enabled questions are answered."""
    domain = await _resolve_domain(db, code)
    if domain["contributor_id"] != contributor_id:
        raise AuthorizationError("domain not assigned to this user", code="forbidden")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError("domain is read-only", code="domain_read_only")

    questions = await _load_answered_questions(
        db, domain_id=domain["id"], contributor_id=contributor_id
    )
    if not questions:
        raise ConflictError("no enabled questions to compile", code="no_questions")

    conversation: list[dict[str, Any]] = []
    for q in questions:
        item = {
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
        conversation.append(item)

    crew = CompilerCrew(
        db,
        domain_code=code,
        domain_name=domain["name"],
        conversation=conversation,
        llm=llm,
    )
    try:
        narrative = await crew.compile()
    except Exception as exc:
        raise ExternalServiceError(
            "compilation failed; please retry",
            code="llm_unavailable",
        ) from exc

    await db.execute(
        """
        INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at)
        VALUES (?, ?, ?)
        ON CONFLICT(domain_id) DO UPDATE SET
            narrative_text=excluded.narrative_text,
            compiled_at=excluded.compiled_at
        """,
        (domain["id"], narrative, _now()),
    )
    await audit(
        db,
        actor_user_id=contributor_id,
        event_type="domain_compiled",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await db.commit()

    return {
        "domain_id": domain["id"],
        "narrative_text": narrative,
        "compiled_at": _now(),
    }


async def submit_domain(
    db: TenantDB,
    *,
    contributor_id: int,
    code: str,
) -> dict:
    """Submit a compiled domain for reviewer approval."""
    domain = await _resolve_domain(db, code)
    if domain["contributor_id"] != contributor_id:
        raise AuthorizationError("domain not assigned to this user", code="forbidden")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError(
            "domain is already submitted or approved",
            code="domain_already_submitted",
        )

    progress = await get_domain_progress(db, user_id=contributor_id, code=code)
    if not progress["submit_ready"]:
        raise ConflictError("domain is not ready for submission", code="domain_not_ready")

    compiled = await db.fetchone(
        "SELECT id FROM compiled_answers WHERE domain_id = ?",
        (domain["id"],),
    )
    if compiled is None:
        raise ConflictError("domain has not been compiled", code="domain_not_compiled")

    await db.execute(
        "UPDATE domains SET status = 'in_review' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=contributor_id,
        event_type="domain_submitted",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["reviewer_id"],
        kind="domain_submitted",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "in_review",
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


async def _load_answered_questions(
    db: TenantDB,
    *,
    domain_id: int,
    contributor_id: int,
) -> list[dict[str, Any]]:
    questions = await db.fetchall(
        "SELECT * FROM questions WHERE domain_id = ? AND enabled = 1 ORDER BY position",
        (domain_id,),
    )
    result: list[dict[str, Any]] = []
    for q in questions:
        answer = await db.fetchone(
            "SELECT * FROM answers WHERE question_id = ? AND contributor_id = ?",
            (q["id"], contributor_id),
        )
        if answer is None:
            raise ConflictError(
                "not all questions are answered",
                code="questions_unanswered",
            )
        answer_dict = dict(answer)
        if answer_dict["skipped"]:
            raise ConflictError(
                "skipped questions block compilation",
                code="question_skipped",
            )
        if answer_dict["followups_state"] == "pending":
            raise ConflictError("follow-ups pending", code="followups_pending")

        answer_dict["followups"] = await followups_service.get_followups_for_answer(
            db, answer_id=answer_dict["id"]
        )
        result.append({"text": q["text"], "answer": answer_dict})
    return result
