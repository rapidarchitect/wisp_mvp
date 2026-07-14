# Task 14 — Compilation and Submission Design

**Date:** 2026-07-14  
**Task:** 14  
**Scenarios:** QSTN-02, QSTN-03  
**Constraints:** C-12 (domain is read-only for contributor while `in_review`), C-19 (AI outage degrades gracefully)

## Decisions

- **Compilation** is triggered by the contributor via `POST /domains/{code}/compile`.
  - Allowed only when every enabled question has a saved answer and no question is skipped or has pending follow-ups.
  - The `CompilerCrew` reads the full domain conversation (questions, answers, follow-up responses) and writes a single `CompiledAnswer` narrative.
  - On AI failure after retry, the domain remains in its previous state and a clear 503/409 style error is returned so the user can retry (C-19).
- **Submission** is a separate `POST /domains/{code}/submit` action.
  - Requires an existing compiled answer and `submit_ready == True`.
  - Transitions `domains.status` to `in_review`, locking the contributor out of further edits (C-12).
  - Notifies the assigned reviewer.
- The existing `GET /domains/{code}/progress` already returns `submit_ready`; Task 14 adds the compile and submit endpoints.
- Feature-file changes for QSTN-02 and QSTN-03 require human approval per `AGENTS.md`.

## Data model

No schema changes required.

- `compiled_answers` table stores `domain_id`, `narrative_text`, `compiled_at`.
- `domains.status` transitions `assigned -> in_progress -> in_review`.
- `domain_assignments` provides contributor/reviewer ids.

## Service API

### `app/services/compilation.py`

#### `compile_domain(db, *, contributor_id, code, llm=None) -> dict`

1. Resolve current in-progress version and domain by code.
2. Verify user is assigned contributor and domain status is not `in_review` or `approved`.
3. Load every enabled question with its answer.
   - Raise `ConflictError` if any enabled question has no answer.
   - Raise `ConflictError` if any answer is skipped (C-11 already enforced here).
   - Raise `ConflictError` if any answer has followups_state == `pending`.
4. Call `CompilerCrew(...).compile()` with conversation snapshot.
5. On success, insert or replace `compiled_answers` row for the domain and return it.
6. Audit `domain_compiled`.
7. On failure, raise `ExternalServiceError` / `ConflictError` with code `llm_unavailable` so caller can retry (C-19). Do not transition domain state.

#### `submit_domain(db, *, contributor_id, code) -> dict`

1. Resolve domain and verify contributor assignment.
2. Verify domain status is `in_progress` or `assigned` (not already `in_review`/`approved`).
3. Load progress via existing helper; raise `ConflictError` if `submit_ready` is false.
4. Verify a compiled answer exists for the domain.
5. Set `domains.status = 'in_review'`.
6. Notify reviewer with `domain_submitted`.
7. Audit `domain_submitted`.
8. Return domain summary.

### `app/crews/compiler_crew.py`

#### `CompilerCrew`

- Inputs: `domain_code`, `domain_name`, and conversation list of `{"question": str, "answer": str, "followups": [{"text": str, "response": str}]}`. Optional `llm`.
- Builds a prompt asking the LLM to return a single professional WISP narrative paragraph.
- Uses `CrewBase.run_with_retry(self._compile_once, max_retries=1)`.
- `_compile_once` calls the LLM and returns the raw narrative string.
- No parsing beyond stripping leading/trailing whitespace.

## HTTP routes (`app/api/routers/compilation.py`)

Mounted without prefix (includes `tenant` middleware) as existing routers are.

- `POST /domains/{code}/compile` — contributor
- `POST /domains/{code}/submit` — contributor

## Notifications and audit

- `notification_templates.py` additions:
  - `domain_submitted`: "The {domain_name} domain has been submitted for review."
- Audit events:
  - `domain_compiled`
  - `domain_submitted`

## BDD scenarios

Add these scenarios to `features/contributor-questionnaire.feature` (requires human approval):

```gherkin
  Scenario: QSTN-02 AI compiles the domain final answer
    Given a fully answered domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" compiles domain "AC"
    Then the compiled answer narrative is non-empty
    And a "domain_compiled" audit event exists for domain "AC"

  Scenario: QSTN-03 Contributor submits the domain for review
    Given a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" submits domain "AC"
    Then the domain "AC" status is "in_review"
    And the reviewer receives a "domain_submitted" notification
```

## Testing plan

- Unit tests:
  - `tests/unit/test_compiler_crew.py`
  - `tests/unit/test_services_compilation.py`
  - `tests/unit/test_routers_compilation.py`
- BDD step definitions added to `tests/steps/test_contributor_questionnaire.py`.
- Playwright API smoke test `frontend/e2e/compilation.spec.ts` covering compile + submit.
- Full BDD suite and lint must remain green.
