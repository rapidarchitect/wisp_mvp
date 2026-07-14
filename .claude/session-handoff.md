# Session Handoff — WISPGen

**Date:** 2026-07-14 05:40 UTC  
**Branch:** `task-12-domain-assignment`  
**Last completed task:** Task 13 (Contributor Questionnaire Flow)

## Completed tasks

| Task | Branch | Status | Key deliverables |
|------|--------|--------|------------------|
| Task 01 | `task-01-scaffold` | committed on `main` | Repo scaffold, toolchain, docs aligned |
| Task 02 | `task-02-tenancy` | committed | Control DB, tenant DB factory, middleware, services, unit tests (C-01) |
| Task 03 | `task-03-auth-core` | committed | Argon2id passwords, sessions, lockout, audit log (C-02, C-03, C-05, AUTH-03, AUTH-05, AUTH-06) |
| Task 04 | `task-04-totp` | committed | Mandatory TOTP enrollment + TOTP-protected login (C-04, AUTH-01, AUTH-02, AUTH-04) |
| Task 05 | `task-05-password-reset` | committed | Signed 30-min reset tokens, console email backend (C-06, AUTH-07) |
| Task 06 | `task-06-signup-provisioning` | committed | Signup, corporate vitals, voucher/card payment, tenant provisioning, 14 domains (C-01, C-17, SIGN-01..SIGN-05) |
| Task 07 | `task-07-user-role-management` | committed | 7-day invitations, activation with password + TOTP, multi-role grants, duplicate/expired invite rejection, deactivation unassigns domains while preserving answers (C-09, C-10, C-11, USER-01..USER-06) |
| Task 08 | `task-08-llm-factory` | committed | Configurable LLM factory, crew retry base with exponential backoff, Tavily tool wrapper, deterministic fake doubles (C-19) |
| Task 09 | `task-09-domain-seeding` | committed | SeederCrew generates 5-10 yes-no questions per domain, `seed-demo` CLI provisions and seeds demo tenant, LLM outage marks domains `pending_questions` gracefully (C-08, C-19, SEED-01..SEED-03) |
| Task 10 | `task-10-questions-service` | committed | Admin question add/edit/disable/reinstate, per-domain regeneration guarded by zero answers, shared auth dependencies, atomic validation (C-08, C-16, SEED-04..SEED-06) |
| Task 11 | `task-11-email-backends` | committed | Notifications service, in-app feed endpoint, console/SES email backends with singleton factory, `notify()` wired into invitations, role changes, and deactivation (Task 11 scenario-exempt) |
| Task 12 | `task-12-domain-assignment` | committed | Domain assignment service/router, exactly one contributor + one reviewer per domain, role-scoped visibility, admin gap flag, BDD scenarios ASSN-01..05 green, Playwright API smoke tests (C-10) |
| Task 13 | `task-12-domain-assignment` | committed (current branch) | Contributor questionnaire flow: `save_answer`, `save_followup_response`, `get_domain_progress`, `FollowUpCrew` with cap and retry, AI outage waiver (C-09, C-11, C-19), QSTN-01/04/05/06 green, Playwright API smoke test |

## Current verification

- `uv run pytest tests/ -q` → **119 passed**
- `uv run pytest tests/steps -q` → **37 passed**
- `uv run pytest tests/unit/test_services_answers.py tests/unit/test_routers_questionnaire.py tests/unit/test_followups_service.py tests/unit/test_followup_crew.py -q` → **17 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `npm run test:e2e -- questionnaire.spec.ts` (with backend running, `LLM_PROVIDER=fake`) → **1 passed**
- `TESTPLAN.md` statuses updated: SIGN-01..05, AUTH-01..07, USER-01..06, SEED-01..06, ASSN-01..05, **QSTN-01/04/05/06 green**.

## Active files of note

- `app/services/answers.py` — answer persistence, follow-up orchestration, progress, AI outage fallback.
- `app/services/followups.py` — follow-up persistence helpers.
- `app/crews/followup_crew.py` — generates up to 3 follow-up questions with one retry.
- `app/api/routers/questionnaire.py` — `/questions/{id}/answer`, `/followups/{id}/respond`, `/domains/{code}/progress`.
- `app/services/notification_templates.py` — `answer_saved`, `followups_waived` templates.
- `tests/unit/test_services_answers.py` — unit tests for answer lifecycle, skip blocking, AI outage waiver, submit readiness.
- `tests/unit/test_routers_questionnaire.py` — router auth/response tests.
- `tests/unit/test_followups_service.py` — follow-up persistence unit tests.
- `tests/unit/test_followup_crew.py` — follow-up generation and retry unit tests.
- `tests/steps/test_contributor_questionnaire.py` — BDD step definitions for QSTN-01/04/05/06.
- `features/contributor-questionnaire.feature` — QSTN-01/04/05/06 scenarios.
- `frontend/e2e/questionnaire.spec.ts` — Playwright API smoke test for the questionnaire flow.
- `frontend/e2e/setup.py` — seeds demo tenant with deterministic fake questions for e2e.

## Known technical notes

- BDD step functions are **synchronous** and use `sqlite3` for direct DB assertions, plus `TestClient` for HTTP.
- Cross-feature Givens live in `tests/steps/common_steps.py`; `tests/conftest.py` registers them via `pytest_plugins`.
- `tests/steps/helpers.py` holds shared step utilities like `_tenant_db_path`.
- Answer service writes audit events inside the immediate transaction; notifications are sent after commit so email failures do not roll back the answer.
- E2E tests run against `demo.localhost:8000` with `Host` header; the backend must be started with `LLM_PROVIDER=fake` for deterministic follow-up generation.
- When follow-up generation returns an empty list, the answer is marked `complete` immediately so contributors are not blocked.
- When follow-up generation fails after one retry, the answer's `followups_state` is set to `waived`, a notification is created, and the answer is treated as complete for submission (C-19).

## Next task: Task 14

**Objective:** Review workflow (QSTN-02, QSTN-03, REVW-01..05) — AI compilation of domain answers, contributor submission, reviewer approval/deferral, self-review warning, WISP completion.

**Key constraints:**
- Contributor can compile and submit a domain for review once all questions are answered/skipped appropriately.
- Reviewer can approve, request revision, or defer.
- Direct approval by the same contributor is allowed with a warning.
- All 14 domains approved completes the WISP.

**Verification target:**
- QSTN-02, QSTN-03, REVW-01..05 green.
- Coverage on `app/services` ≥ 85%.
