# Task 15 — Review Workflow Design

**Date:** 2026-07-14  
**Task:** 15  
**Scenarios:** REVW-01, REVW-02, REVW-03, REVW-04, REVW-05  
**Constraints:** C-12 (read-only for contributor while `in_review`), C-19 (AI outage degrades gracefully)

## Decisions

- **Review actions** are performed by the assigned reviewer via a new `review.py` service and router:
  - `POST /domains/{code}/approve` — marks the compiled answer approved, sets domain status to `approved`, notifies the contributor.
  - `POST /domains/{code}/revise` — accepts `revision_prompt`, runs `RevisionCrew` to rewrite the narrative, stores the new narrative, sets `revised_by_reviewer_id`, and immediately approves.
  - `POST /domains/{code}/defer` — sets domain status back to `in_progress` so the contributor can add information; compiled answer is preserved.
- **Self-review warning:** when `reviewer_id == contributor_id`, the response includes `self_review: true` but the action still succeeds (REVW-04).
- **Version completion:** when the 14th domain in the current version is approved, mark the version `status = 'complete'`, set `completed_at`, notify the admin, and audit `wisp_completed`.
- **AI outage** during revision raises `ExternalServiceError` with code `llm_unavailable`; domain and compiled answer remain unchanged (C-19).

## Data model

No schema changes required.

- `compiled_answers` columns used: `domain_id`, `narrative_text`, `compiled_at`, `revised_by_reviewer_id`, `approved_at`.
- `domains.status` transitions: `in_review → approved` or `in_review → in_progress`.
- `wisp_versions.status` transitions: `in_progress → complete`.

## Service API

### `app/services/review.py`

#### `approve_domain(db, *, reviewer_id, code) → dict`

1. Resolve current version and domain by code.
2. Verify the user is the assigned reviewer.
3. Verify domain status is `in_review`.
4. Update `compiled_answers.approved_at` and `domains.status = 'approved'`.
5. Notify contributor with `domain_approved`.
6. Audit `domain_approved`.
7. Check if all 14 domains in the version are `approved`.
   - If yes: set `wisp_versions.status = 'complete'`, `completed_at = now`, notify admin with `wisp_complete`, audit `wisp_completed`.
   - Return domain summary with `wisp_complete: true` and `self_review: true` when reviewer == contributor.

#### `revise_and_approve(db, *, reviewer_id, code, revision_prompt, llm=None) → dict`

1. Resolve domain and verify reviewer.
2. Verify domain status is `in_review`.
3. Load the existing compiled answer and full domain conversation (reuse `compilation._load_answered_questions`).
4. Call `RevisionCrew(...).revise(revision_prompt)`.
5. On success: update `compiled_answers.narrative_text`, set `revised_by_reviewer_id`, then call `approve_domain` logic.
6. Notify contributor with `domain_revised_and_approved`.
7. On failure: raise `ExternalServiceError` without changing state (C-19).

#### `defer_domain(db, *, reviewer_id, code) → dict`

1. Resolve domain and verify reviewer.
2. Verify domain status is `in_review`.
3. Set `domains.status = 'in_progress'`.
4. Audit `domain_deferred`.
5. Notify contributor with `domain_deferred`.

### `app/crews/revision_crew.py`

#### `RevisionCrew`

- Inputs: `domain_code`, `domain_name`, `current_narrative`, full conversation list, optional `llm`.
- Builds a prompt asking the LLM to revise the narrative according to the reviewer prompt.
- Uses `CrewBase.run_with_retry(self._revise_once, max_retries=1)`.
- Returns the revised narrative string.

## HTTP routes (`app/api/routers/review.py`)

Mounted without prefix as other tenant routers.

- `POST /domains/{code}/approve` — reviewer
- `POST /domains/{code}/revise` — reviewer (body: `{"revision_prompt": str}`)
- `POST /domains/{code}/defer` — reviewer

## Notifications and audit

- `notification_templates.py` additions:
  - `domain_approved`
  - `domain_revised_and_approved`
  - `domain_deferred`
  - `wisp_complete`
- Audit events:
  - `domain_approved`
  - `domain_revised`
  - `domain_deferred`
  - `wisp_completed`

## BDD scenarios

Create `features/review-workflow.feature` with REVW-01..05.

```gherkin
Feature: Review workflow

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled user "admin@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "admin"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "SecurePass123!" and roles "reviewer"
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is signed in
    And a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"
    And "contributor@palmetto.app.wisp.llc" submits domain "AC"
    And "reviewer@palmetto.app.wisp.llc" is signed in

  Scenario: REVW-01 Reviewer approves compiled answer
    When the reviewer approves domain "AC"
    Then the domain "AC" status is "approved"
    And the contributor receives a "domain_approved" notification

  Scenario: REVW-02 Edit produces AI revision and direct approval
    When the reviewer revises domain "AC" with prompt "Add more detail on access logs"
    Then the compiled answer narrative contains "access logs"
    And the domain "AC" status is "approved"
    And the contributor receives a "domain_revised_and_approved" notification

  Scenario: REVW-03 Reviewer defers decision
    When the reviewer defers domain "AC"
    Then the domain "AC" status is "in_progress"

  Scenario: REVW-04 Self-review shows warning
    Given domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "contributor@palmetto.app.wisp.llc" as reviewer
    When the reviewer approves domain "AC"
    Then the response includes a self-review warning

  Scenario: REVW-05 All approved completes the WISP
    Given all 14 domains are submitted for "contributor@palmetto.app.wisp.llc"
    When the reviewer approves the last domain
    Then the WISP version status is "complete"
    And the admin receives a "wisp_complete" notification
```

Note: REVW-04 will reassign the domain so reviewer == contributor. The background signs in reviewer first; REVW-04 will need to sign in the contributor (now reviewer).

## Testing plan

- Unit tests:
  - `tests/unit/test_revision_crew.py`
  - `tests/unit/test_services_review.py`
  - `tests/unit/test_routers_review.py`
- BDD step definitions in `tests/steps/test_review_workflow.py`.
- Playwright API smoke test `frontend/e2e/review-workflow.spec.ts`.
- Full BDD suite and lint must remain green.
