# Task 13 — Questionnaire Flow Design

**Date:** 2026-07-13  
**Task:** 13  
**Scenarios:** QSTN-01, QSTN-04, QSTN-05, QSTN-06  
**Constraints:** C-09 (at most 3 follow-ups per question), C-11 (skipped questions block submission), C-19 (AI outage degrades gracefully)

## Decisions

- Follow-up generation is **synchronous** inside `save_answer`. The service calls `FollowUpCrew` immediately after persisting a non-skipped answer and returns the generated follow-ups in the response.
- Generated follow-ups **require contributor responses**. The answer's `followups_state` becomes `complete` only after every follow-up has a non-empty `response_text`.
- Skipping a question is a flag on the same `POST /questions/{question_id}/answer` endpoint: payload contains either `value` (yes/no) or `skipped: true`.
- Save/resume is exposed through a dedicated `GET /domains/{code}/progress` endpoint that returns the full per-question state plus a `submit_ready` boolean.
- AI outage is handled by `CrewBase.run_with_retry` with one retry; after two failures the service marks `followups_state = waived`, notifies the contributor, and treats the answer as complete for submission purposes (C-19).

## Data model

No schema changes are required. The existing tables are sufficient:

- `answers` stores the question response, `skipped`, and `followups_state` (`pending`, `complete`, `waived`).
- `followups` stores each generated follow-up with `text`, optional `response_text`, and `position` (1–3).
- `domains.status` transitions from `assigned` to `in_progress` when the first answer is saved.

## Service API

### `app/services/answers.py`

#### `save_answer(db, *, contributor_id: int, question_id: int, value: str | None = None, skipped: bool = False) -> dict`

1. Load the question and its domain. Raise `NotFoundError` if missing.
2. Verify the domain is assigned to this contributor and that its status is not `in_review` or `approved` (C-12).
3. If the question already has a final answer (`skipped` or non-skipped with followups complete/waived), raise `ConflictError` unless the caller is explicitly editing.
4. Upsert the `answers` row:
   - `value` is set when not skipped.
   - `skipped` is set to true when skipped.
   - `followups_state` starts as `pending` for non-skipped answers.
5. If not skipped and `followups_state == pending`:
   - Call `FollowUpCrew(db, answer_id=..., domain_code=..., domain_name=..., answer_value=..., answer_text=...).generate()`.
   - On success, insert 1–3 follow-up rows and leave state `pending` until responses are saved.
   - On failure after retry, set `followups_state = waived`, create a notification for the contributor, and write an audit event.
6. If the domain status is `assigned`, update it to `in_progress`.
7. Return the answer record including generated follow-ups.

#### `save_followup_response(db, *, contributor_id: int, followup_id: int, response_text: str) -> dict`

1. Load the follow-up and its parent answer. Verify the answer belongs to the contributor.
2. Store the trimmed `response_text`.
3. Check whether all follow-ups for this answer have responses. If so, set `answers.followups_state = complete`.
4. Return the updated follow-up.

#### `get_domain_progress(db, *, user_id: int, code: str) -> dict`

1. Resolve the current in-progress version and the domain by code.
2. Verify the user is the assigned contributor for this domain.
3. Return:
   - `domain_id`, `code`, `name`, `status`
   - `questions`: list of every enabled question with `id`, `text`, `position`, `answer` (value/skipped/followups_state), and `followups` (text + response_text)
   - `submit_ready`: true when every enabled question is answered or skipped, no question is skipped, and every answer's `followups_state` is `complete` or `waived`

### `app/crews/followup_crew.py`

#### `FollowUpCrew`

- Accepts `answer_id`, `domain_code`, `domain_name`, `answer_value`, `answer_text`, and optional `llm`.
- Builds a prompt asking the LLM to generate up to three short follow-up questions that dig deeper into the answer.
- Uses the Tavily tool (via `app.ai.tavily_tool`) to ground the prompt with industry context when a real LLM is configured.
- Wraps the call with `CrewBase.run_with_retry(max_retries=1)` so a single transient failure recovers.
- Parses the LLM response into a list of follow-up texts. If more than 3 are returned, truncate to 3 (C-09).

### `app/services/followups.py`

Thin helper for follow-up persistence, used by the service and crew:

- `insert_followups(db, answer_id, texts) -> list[dict]` — inserts rows with positions 1, 2, 3.
- `get_followups_for_answer(db, answer_id) -> list[dict]` — returns all follow-ups ordered by position.

## HTTP routes (`app/api/routers/questionnaire.py`)

Mounted under the tenant router.

- `POST /questions/{question_id}/answer`
  - Body: `{"value": "yes" | "no"}` or `{"skipped": true}`
  - Response: answer record with generated follow-ups
- `POST /followups/{followup_id}/respond`
  - Body: `{"response_text": str}`
  - Response: updated follow-up
- `GET /domains/{code}/progress`
  - Response: domain progress object including `submit_ready`

All endpoints require an authenticated user and enforce the contributor role where applicable.

## Notifications and audit

- `answer_saved` notification sent to the contributor after each answer.
- `followups_waived` notification sent when AI outage prevents follow-up generation (C-19).
- Audit events:
  - `answer_saved` with question id and skipped flag
  - `followups_waived` with answer id and domain code

## BDD scenarios (`features/contributor-questionnaire.feature`)

- **QSTN-01** — Answering a question generates up to 3 follow-ups.
- **QSTN-04** — Skipped questions block submission (`submit_ready: false`).
- **QSTN-05** — Contributor saves progress, leaves, and resumes to find the exact same answered/skipped/follow-up state.
- **QSTN-06** — Fake LLM failing twice waives follow-ups; the answer becomes complete and the contributor is notified.

## Testing plan

- Unit tests in `tests/unit/test_services_answers.py` cover:
  - Saving and skipping answers.
  - Contributor authorization and read-only domain guards.
  - Follow-up generation and the 3-follow-up cap (C-09).
  - Follow-up response flow marking an answer complete.
  - AI outage fallback path marking state `waived` and sending a notification (C-19).
  - Domain progress calculation and `submit_ready` logic including skipped-block (C-11).
- BDD step definitions in `tests/steps/test_contributor_questionnaire.py` implement the four scenarios.
- Full BDD suite and lint must remain green.
