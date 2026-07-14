"""Answer service: contributor questionnaire flow and progress tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.crews.followup_crew import FollowUpCrew
from app.db.tenant import TenantDB
from app.exceptions import AuthorizationError as ForbiddenError
from app.exceptions import ConflictError, NotFoundError
from app.services import followups
from app.services.audit import audit
from app.services.notifications import notify


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def save_answer(
    db: TenantDB,
    *,
    contributor_id: int,
    question_id: int,
    value: str | None = None,
    skipped: bool = False,
    llm: Any | None = None,
) -> dict:
    """Persist an answer and generate follow-up questions.

    On follow-up generation failure after retry, the answer's follow-up state
    is waived so the contributor is not blocked (C-19).
    """
    row = await db.fetchone(
        """
        SELECT q.id as question_id, q.domain_id, q.text, q.position, q.enabled,
               d.id as domain_id, d.code, d.name, d.status,
               a.contributor_id
        FROM questions q
        JOIN domains d ON d.id = q.domain_id
        LEFT JOIN domain_assignments a ON a.domain_id = d.id
        WHERE q.id = ?
        """,
        (question_id,),
    )
    if row is None:
        raise NotFoundError("question not found")

    domain = dict(row)
    if domain["contributor_id"] != contributor_id:
        raise ForbiddenError("domain not assigned to this user")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError("domain is read-only", code="domain_read_only")
    if not domain["enabled"]:
        raise ConflictError("question is disabled", code="question_disabled")

    existing = await db.fetchone(
        "SELECT id, value, skipped, followups_state FROM answers WHERE question_id = ?",
        (question_id,),
    )
    if existing:
        state = existing["followups_state"]
        if existing["skipped"] or state in ("complete", "waived"):
            raise ConflictError("question already answered", code="already_answered")

    followups_state = "complete" if skipped else "pending"

    await db.execute(
        """
        INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            contributor_id=excluded.contributor_id,
            value=excluded.value,
            skipped=excluded.skipped,
            followups_state=excluded.followups_state
        """,
        (question_id, contributor_id, value, int(skipped), followups_state),
    )
    await db.commit()
    answer_id = (await db.fetchone("SELECT id FROM answers WHERE question_id = ?", (question_id,)))[
        0
    ]

    generated_followups: list[dict] = []
    if not skipped and followups_state == "pending":
        crew = FollowUpCrew(
            db,
            answer_id=answer_id,
            domain_code=domain["code"],
            domain_name=domain["name"],
            answer_value=value or "",
            answer_text="",
            llm=llm,
        )
        try:
            texts = await crew.generate()
            if not texts:
                await db.execute(
                    "UPDATE answers SET followups_state = 'complete' WHERE id = ?",
                    (answer_id,),
                )
                await db.commit()
                followups_state = "complete"
            else:
                generated_followups = await followups.insert_followups(
                    db, answer_id=answer_id, texts=texts
                )
        except Exception:
            await db.execute(
                "UPDATE answers SET followups_state = 'waived' WHERE id = ?",
                (answer_id,),
            )
            await db.commit()
            followups_state = "waived"
            await notify(
                db,
                user_id=contributor_id,
                kind="followups_waived",
                payload={"answer_id": answer_id},
                channel="in_app",
            )
            await audit(
                db,
                actor_user_id=contributor_id,
                event_type="followups_waived",
                subject=f"answer:{answer_id}",
                detail=f"domain_code={domain['code']}",
                commit=False,
            )
            await db.commit()

    if domain["status"] == "assigned":
        await db.execute(
            "UPDATE domains SET status = 'in_progress' WHERE id = ?",
            (domain["domain_id"],),
        )
        await db.commit()

    await notify(
        db,
        user_id=contributor_id,
        kind="answer_saved",
        payload={"question_id": question_id},
        channel="in_app",
    )
    await audit(
        db,
        actor_user_id=contributor_id,
        event_type="answer_saved",
        subject=f"question:{question_id}",
        detail=f"skipped={skipped}",
        commit=False,
    )
    await db.commit()

    return await _build_answer_dict(db, answer_id, generated_followups, followups_state)


async def _build_answer_dict(
    db: TenantDB, answer_id: int, followup_rows: list[dict], state: str
) -> dict:
    row = await db.fetchone("SELECT * FROM answers WHERE id = ?", (answer_id,))
    answer = dict(row)
    answer["followups_state"] = state
    answer["followups"] = followup_rows or await followups.get_followups_for_answer(
        db, answer_id=answer_id
    )
    return answer


async def save_followup_response(
    db: TenantDB,
    *,
    contributor_id: int,
    followup_id: int,
    response_text: str,
) -> dict:
    """Store a contributor's response to a follow-up question."""
    row = await db.fetchone(
        """
        SELECT f.id, f.answer_id, a.contributor_id, a.followups_state
        FROM followups f
        JOIN answers a ON a.id = f.answer_id
        WHERE f.id = ?
        """,
        (followup_id,),
    )
    if row is None:
        raise NotFoundError("followup not found")
    if row["contributor_id"] != contributor_id:
        raise ForbiddenError("not your followup")

    updated = await followups.save_followup_response(
        db, followup_id=followup_id, response_text=response_text
    )

    all_followups = await followups.get_followups_for_answer(db, answer_id=row["answer_id"])
    if all(f.get("response_text") for f in all_followups):
        await db.execute(
            "UPDATE answers SET followups_state = 'complete' WHERE id = ?",
            (row["answer_id"],),
        )
    else:
        await db.execute(
            "UPDATE answers SET followups_state = 'pending' WHERE id = ?",
            (row["answer_id"],),
        )
    await db.commit()

    return updated


async def get_domain_progress(db: TenantDB, *, user_id: int, code: str) -> dict:
    """Return the contributor's saved progress for a domain plus submit readiness."""
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
    domain_dict = dict(domain)
    if domain_dict["contributor_id"] != user_id and domain_dict.get("reviewer_id") != user_id:
        raise ForbiddenError("domain not assigned to this user")

    questions = await db.fetchall(
        "SELECT * FROM questions WHERE domain_id = ? AND enabled = 1 ORDER BY position",
        (domain["id"],),
    )

    question_list: list[dict] = []
    submit_ready = True
    for q in questions:
        answer_row = await db.fetchone(
            "SELECT * FROM answers WHERE question_id = ? AND contributor_id = ?",
            (q["id"], user_id),
        )
        if answer_row is None:
            submit_ready = False
            question_list.append(
                {
                    "id": q["id"],
                    "text": q["text"],
                    "position": q["position"],
                    "answer": None,
                }
            )
            continue

        answer = dict(answer_row)
        answer["followups"] = await followups.get_followups_for_answer(db, answer_id=answer["id"])
        question_list.append(
            {
                "id": q["id"],
                "text": q["text"],
                "position": q["position"],
                "answer": answer,
            }
        )

        if answer["skipped"] or answer["followups_state"] not in ("complete", "waived"):
            submit_ready = False

    return {
        "domain_id": domain["id"],
        "code": domain["code"],
        "name": domain["name"],
        "status": domain["status"],
        "questions": question_list,
        "submit_ready": submit_ready,
    }
