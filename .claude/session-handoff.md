# Session Handoff — WISPGen

**Date:** 2026-07-13 09:15 UTC  
**Branch:** `task-10-questions-service`  
**Last completed task:** Task 10 (Question Management)

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
| Task 10 | `task-10-questions-service` | committed (current branch) | Admin question add/edit/disable/reinstate, per-domain regeneration guarded by zero answers, shared auth dependencies, atomic validation (C-08, C-16, SEED-04..SEED-06) |

## Current verification

- `uv run pytest tests/ -q` → **all green**
- `uv run pytest tests/steps -q` → **all green**
- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "seed04 or seed05 or seed06"` → **3 passed**
- `uv run pytest tests/unit/test_questions_service.py -q` → **9 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `uv run pytest --cov=app/services --cov-report=term-missing tests/unit/test_questions_service.py` → **93%+ coverage**
- `TESTPLAN.md` statuses updated to **green** for SIGN-01..05, AUTH-01..07, USER-01..06, SEED-01..06.

## Active files of note

- `app/services/questions.py` — `add_question`, `edit_question`, `disable_question`, `reinstate_question`, `regenerate_domain_questions` with atomic `BEGIN IMMEDIATE` transactions and generate-before-delete regeneration.
- `app/api/routers/questions.py` — admin-only `/questions` CRUD and `/domains/{id}/regenerate-questions` endpoints.
- `app/api/dependencies.py` — shared `get_current_user` and `require_admin` dependencies extracted from the users router.
- `app/models/questions.py` — `AddQuestionRequest`, `EditQuestionRequest`.
- `tests/unit/test_questions_service.py` — unit tests for service functions and guardrails.
- `tests/steps/test_domain_seeding_and_questions.py` — BDD step definitions for SEED-01..06.
- `features/domain-seeding-and-questions.feature` — extended with SEED-04..06.

## Known technical notes

- BDD step functions are **synchronous** and use `sqlite3` for direct DB assertions, plus `TestClient` for HTTP.
- `given_domain_is_ready` ensures a domain is ready by seeding it synchronously when needed; this is a pragmatic setup/verification step because the shared Background leaves domains in `pending_questions`.
- All LLM/Tavily calls in the test suite use fakes; no real model or network is invoked.
- The `provisioned_tenant` fixture does **not** eagerly seed domains, preserving SEED-01..03 semantics.

## Next task: Task 11

**Objective:** Notifications service — in-app feed endpoint, console/SES email backend, single `notify()` service used by all workflows. Scenario-exempt as a standalone feature, but every "should be notified" Then step across USER/ASSN/QSTN/REVW scenarios exercises it.

**Files likely to create/modify (per master plan):**
- `app/models/notification.py`, `app/services/notifications.py`, `app/api/routers/notifications.py`, `tests/unit/test_services_notifications.py`
- Modify `app/db/schema/tenant.sql`, `app/main.py`, `app/config.py`, `tests/steps/conftest.py`

**Key constraints:**
- Single `notify(db, user_id, kind, payload)` signature used by all workflows.
- Console backend in dev/test, SES in prod.

**Verification target:**
- `uv run pytest tests/unit/test_services_notifications.py -q` green.
- Coverage on `app/services` ≥ 85%.
