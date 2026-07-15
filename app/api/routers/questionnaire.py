"""Contributor questionnaire API router (Task 13)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.answers import (
    get_domain_progress,
    save_answer,
    save_followup_response,
)

router = APIRouter()


@router.post("/questions/{question_id}/answer")
async def answer_question(
    request: Request,
    question_id: int,
    payload: dict[str, Any],
    authorization: str = Header(...),
) -> dict:
    """Save a contributor's answer to a question and generate follow-ups."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    llm = getattr(request.app.state, "llm", None)
    return await save_answer(
        db,
        contributor_id=user["id"],
        question_id=question_id,
        value=payload.get("value"),
        skipped=payload.get("skipped", False),
        llm=llm,
    )


@router.post("/followups/{followup_id}/respond")
async def respond_to_followup(
    request: Request,
    followup_id: int,
    payload: dict[str, Any],
    authorization: str = Header(...),
) -> dict:
    """Save a contributor's response to a follow-up question."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await save_followup_response(
        db,
        contributor_id=user["id"],
        followup_id=followup_id,
        response_text=payload["response_text"],
    )


@router.get("/domains/{code}/progress")
async def domain_progress(
    request: Request,
    code: str,
    authorization: str = Header(...),
) -> dict:
    """Return the contributor's saved progress for a domain."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await get_domain_progress(db, user_id=user["id"], code=code)
