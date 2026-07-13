"""Question management business rules and persistence."""

from app.crews.seeder_crew import SeederCrew
from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError, ValidationError


async def _get_domain(db: TenantDB, domain_id: int) -> dict:
    row = await db.fetchone(
        "SELECT id, code, name, status FROM domains WHERE id = ?",
        (domain_id,),
    )
    if row is None:
        raise NotFoundError(f"Domain {domain_id} not found")
    return dict(row)


async def _get_question(db: TenantDB, question_id: int) -> dict:
    row = await db.fetchone(
        "SELECT * FROM questions WHERE id = ?",
        (question_id,),
    )
    if row is None:
        raise NotFoundError(f"Question {question_id} not found")
    return dict(row)


async def _count_enabled_questions(db: TenantDB, domain_id: int) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
        (domain_id,),
    )
    return row[0]


async def _domain_has_answers(db: TenantDB, domain_id: int) -> bool:
    row = await db.fetchone(
        """
        SELECT COUNT(*) FROM answers a
        JOIN questions q ON q.id = a.question_id
        WHERE q.domain_id = ?
        """,
        (domain_id,),
    )
    return row[0] > 0


async def add_question(
    db: TenantDB,
    *,
    domain_id: int,
    text: str,
    position: int | None = None,
) -> dict:
    """Add a custom admin question to a domain."""
    await _get_domain(db, domain_id)
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("Question text is required", code="empty_text")

    await db.execute("BEGIN IMMEDIATE")
    try:
        enabled = await _count_enabled_questions(db, domain_id)
        if enabled >= 10:
            raise ValidationError(
                "Domain already has 10 enabled questions", code="too_many_questions"
            )

        if position is None:
            row = await db.fetchone(
                "SELECT COALESCE(MAX(position), 0) FROM questions WHERE domain_id = ?",
                (domain_id,),
            )
            position = row[0] + 1

        cursor = await db.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, cleaned, "yes_no", "admin", 1, position),
        )
        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "question_id": cursor.lastrowid,
        "domain_id": domain_id,
        "origin": "admin",
        "enabled": True,
    }


async def edit_question(
    db: TenantDB,
    *,
    question_id: int,
    text: str,
) -> dict:
    """Edit a question's text."""
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("Question text is required", code="empty_text")

    question = await _get_question(db, question_id)
    await db.execute(
        "UPDATE questions SET text = ? WHERE id = ?",
        (cleaned, question_id),
    )
    await db.commit()
    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "text": cleaned,
    }


async def disable_question(
    db: TenantDB,
    *,
    question_id: int,
) -> dict:
    """Hide a question from contributors."""
    question = await _get_question(db, question_id)

    await db.execute("BEGIN IMMEDIATE")
    try:
        enabled = await _count_enabled_questions(db, question["domain_id"])
        if enabled <= 5:
            raise ValidationError(
                "Cannot disable: domain would have fewer than 5 enabled questions",
                code="minimum_questions",
            )

        await db.execute(
            "UPDATE questions SET enabled = 0 WHERE id = ?",
            (question_id,),
        )
        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "enabled": False,
    }


async def reinstate_question(
    db: TenantDB,
    *,
    question_id: int,
) -> dict:
    """Make a previously disabled question visible again."""
    question = await _get_question(db, question_id)

    await db.execute("BEGIN IMMEDIATE")
    try:
        enabled = await _count_enabled_questions(db, question["domain_id"])
        if enabled >= 10:
            raise ValidationError(
                "Cannot reinstate: domain already has 10 enabled questions",
                code="too_many_questions",
            )

        await db.execute(
            "UPDATE questions SET enabled = 1 WHERE id = ?",
            (question_id,),
        )
        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "enabled": True,
    }


async def regenerate_domain_questions(
    db: TenantDB,
    *,
    domain_id: int,
    llm=None,
) -> dict:
    """Replace seeded questions with a fresh LLM-generated set.

    Allowed only when the domain has zero answers (C-16). Admin-added custom
    questions are preserved. If the LLM fails, the domain is marked
    pending_questions per C-19 and the previous seeded questions remain.
    """
    domain = await _get_domain(db, domain_id)
    if await _domain_has_answers(db, domain_id):
        raise ConflictError(
            "Domain has answers; regeneration is not allowed", code="domain_has_answers"
        )

    rows = await db.fetchall(
        "SELECT id FROM questions WHERE domain_id = ? AND origin = 'seeded'",
        (domain_id,),
    )
    old_seeded_ids = [row["id"] for row in rows]

    crew = SeederCrew(
        db,
        domain_id=domain_id,
        domain_code=domain["code"],
        domain_name=domain["name"],
        llm=llm,
    )
    result = await crew.seed_domain()

    if result["status"] == "ready" and old_seeded_ids:
        await db.execute(
            f"DELETE FROM questions WHERE id IN ({','.join('?' * len(old_seeded_ids))})",
            tuple(old_seeded_ids),
        )
        await db.commit()

    return result
