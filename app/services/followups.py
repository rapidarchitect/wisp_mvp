"""Follow-up persistence helpers for the questionnaire flow."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.tenant import TenantDB


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def insert_followups(
    db: TenantDB,
    *,
    answer_id: int,
    texts: list[str],
) -> list[dict]:
    """Insert up to three follow-up rows for an answer, ordered by position."""
    rows: list[dict] = []
    for position, text in enumerate(texts[:3], start=1):
        cursor = await db.execute(
            """
            INSERT INTO followups (answer_id, position, text)
            VALUES (?, ?, ?)
            """,
            (answer_id, position, text),
        )
        rows.append(
            {
                "id": cursor.lastrowid,
                "answer_id": answer_id,
                "position": position,
                "text": text,
                "response_text": None,
            }
        )
    await db.commit()
    return rows


async def get_followups_for_answer(
    db: TenantDB,
    *,
    answer_id: int,
) -> list[dict]:
    """Return all follow-ups for an answer, ordered by position."""
    rows = await db.fetchall(
        "SELECT * FROM followups WHERE answer_id = ? ORDER BY position",
        (answer_id,),
    )
    return [dict(row) for row in rows]


async def save_followup_response(
    db: TenantDB,
    *,
    followup_id: int,
    response_text: str,
) -> dict:
    """Persist a contributor's response to a follow-up question."""
    cleaned = response_text.strip()
    await db.execute(
        "UPDATE followups SET response_text = ? WHERE id = ?",
        (cleaned, followup_id),
    )
    await db.commit()
    row = await db.fetchone("SELECT * FROM followups WHERE id = ?", (followup_id,))
    if row is None:
        raise ValueError("followup not found")
    return dict(row)
