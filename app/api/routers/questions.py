"""Question management API router (Task 10)."""

from fastapi import APIRouter, Header, Request

from app.api.routers.users import _get_current_user, _require_admin
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.questions import AddQuestionRequest, EditQuestionRequest
from app.services.questions import (
    add_question,
    disable_question,
    edit_question,
    regenerate_domain_questions,
    reinstate_question,
)

router = APIRouter()
domain_router = APIRouter()


@router.post("")
async def create_question(
    request: Request,
    payload: AddQuestionRequest,
    authorization: str = Header(...),
) -> dict:
    """Add a custom question to a domain."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await add_question(
        db,
        domain_id=payload.domain_id,
        text=payload.text,
        position=payload.position,
    )


@router.patch("/{question_id}")
async def patch_question(
    request: Request,
    question_id: int,
    payload: EditQuestionRequest,
    authorization: str = Header(...),
) -> dict:
    """Edit question text."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await edit_question(db, question_id=question_id, text=payload.text)


@router.post("/{question_id}/disable")
async def question_disable(
    request: Request,
    question_id: int,
    authorization: str = Header(...),
) -> dict:
    """Disable a question."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await disable_question(db, question_id=question_id)


@router.post("/{question_id}/reinstate")
async def question_reinstate(
    request: Request,
    question_id: int,
    authorization: str = Header(...),
) -> dict:
    """Reinstate a disabled question."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await reinstate_question(db, question_id=question_id)


@domain_router.post("/{domain_id}/regenerate-questions")
async def domain_regenerate_questions(
    request: Request,
    domain_id: int,
    authorization: str = Header(...),
) -> dict:
    """Regenerate seeded questions for a domain."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await regenerate_domain_questions(db, domain_id=domain_id)
