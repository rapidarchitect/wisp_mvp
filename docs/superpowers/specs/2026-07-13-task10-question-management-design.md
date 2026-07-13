# Task 10 — Question Management Design

> **Approved:** 2026-07-13  
> **Task:** 10  
> **Scenarios:** SEED-04, SEED-05, SEED-06  
> **Constraints:** C-08 (5–10 yes-no questions per domain), C-16 (regeneration only when unanswered), C-19 (AI outage degrades gracefully)

## Goal

Allow a company admin to manage the questions inside any domain: add custom questions, edit question text, disable seeded questions, reinstate disabled questions, and regenerate a domain’s seeded questions when no answers exist yet.

## Architecture

A single service module owns all question-related business rules and validation. A thin FastAPI router exposes admin-only endpoints, reusing the existing session-token + admin-role dependency pattern from Task 07. The existing `questions` table already supports `origin`, `enabled`, and `position`, so no schema changes are required.

## Data Model

The existing `questions` table:

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | question identifier |
| `domain_id` | INTEGER FK | owning domain |
| `text` | TEXT | question text |
| `answer_type` | TEXT | `yes_no` only |
| `origin` | TEXT | `seeded` or `admin` |
| `enabled` | INTEGER | 1 = visible to contributors, 0 = hidden |
| `position` | INTEGER | display order within the domain |

## Validation Rules

- Question text must be non-empty after stripping.
- Every domain must keep **5–10 enabled questions** at all times.
  - `add_question`: block if enabled count would exceed 10.
  - `disable_question`: block if enabled count would drop below 5.
  - `reinstate_question`: block if enabled count would exceed 10.
- `regenerate_domain_questions` (C-16): allowed only when the domain has **zero answers** across all its questions.
- Regeneration replaces **only** `origin = 'seeded'` questions; admin-added custom questions are preserved.
- If the LLM call during regeneration fails after retry, the domain is marked `pending_questions` per C-19 and can be retried later.

## Service API

```python
async def add_question(
    db: TenantDB, *, domain_id: int, text: str, position: int | None = None
) -> dict: ...

async def edit_question(
    db: TenantDB, *, question_id: int, text: str
) -> dict: ...

async def disable_question(
    db: TenantDB, *, question_id: int
) -> dict: ...

async def reinstate_question(
    db: TenantDB, *, question_id: int
) -> dict: ...

async def regenerate_domain_questions(
    db: TenantDB, *, domain_id: int, llm=None
) -> dict: ...
```

Each function returns a dict with at least `question_id` or `domain_id` plus the new state.

## HTTP API

All endpoints require `Authorization: Bearer <session_token>` and an admin role.

| Method | Path | Action |
|--------|------|--------|
| POST | `/questions` | `add_question` |
| PATCH | `/questions/{question_id}` | `edit_question` |
| POST | `/questions/{question_id}/disable` | `disable_question` |
| POST | `/questions/{question_id}/reinstate` | `reinstate_question` |
| POST | `/domains/{domain_id}/regenerate-questions` | `regenerate_domain_questions` |

Errors use the existing exception hierarchy (`ValidationError`, `ConflictError`, `NotFoundError`) and are translated to the project’s standard error envelope by existing middleware.

## Feature File Scenarios

The following scenarios will be added to `features/domain-seeding-and-questions.feature`:

- **SEED-04 — Admin adds custom question**: Given a signed-in admin and a seeded domain, when the admin adds a custom question, then the question exists with origin `admin` and the enabled count stays within 5–10.
- **SEED-05 — Admin disables seeded question**: Given a signed-in admin and a domain with more than 5 enabled questions, when the admin disables a seeded question, then it is hidden from contributors; attempting to disable when it would drop below 5 is rejected.
- **SEED-06 — Regeneration only when unanswered**: Given a signed-in admin and a domain with zero answers, regeneration succeeds and produces fresh seeded questions; given a domain with at least one answer, regeneration is rejected with `domain_has_answers`.

## Files to Create

- `app/services/questions.py`
- `app/api/routers/questions.py`
- `tests/unit/test_questions_service.py`

## Files to Modify

- `features/domain-seeding-and-questions.feature`
- `tests/steps/test_domain_seeding_and_questions.py`
- `app/main.py` (register the new router)

## Verification

- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "SEED-04 or SEED-05 or SEED-06"` green
- `uv run pytest tests/ -q` green
- `uv run ruff check . && uv run ruff format --check .` clean
- `TESTPLAN.md` matrix updated for SEED-04..06
