# Session Handoff — WISPGen

**Date:** 2026-07-14  
**Branch:** `task-14-compilation-submission`  
**Last completed task:** Task 14 (Compilation and Submission)

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
| Task 13 | `task-13-questionnaire-flow` | committed | Contributor questionnaire flow: `save_answer`, `save_followup_response`, `get_domain_progress`, `FollowUpCrew` with cap and retry, AI outage waiver (C-09, C-11, C-19), QSTN-01/04/05/06 green, Playwright API smoke test |
| Task 14 | `task-14-compilation-submission` | current branch | CompilerCrew, compilation/submission service, compile/submit endpoints, BDD QSTN-02/03 green, Playwright compile+submit smoke (C-12, C-19) |

## Current verification

- `uv run pytest tests/ -q` → **126 passed**
- `uv run pytest tests/steps -q` → **39 passed**
- `uv run pytest tests/unit/test_compiler_crew.py tests/unit/test_services_compilation.py tests/unit/test_routers_compilation.py tests/unit/test_notification_templates.py -q` → **15 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- Playwright `compilation.spec.ts` (with backend running `LLM_PROVIDER=fake`) → **1 passed**
- `TESTPLAN.md` statuses updated: **QSTN-02/03 green**.

## Active files of note

- `app/crews/compiler_crew.py` — generates domain narrative from questions, answers, and follow-up responses.
- `app/services/compilation.py` — `compile_domain` and `submit_domain` with C-12/C-19 enforcement.
- `app/api/routers/compilation.py` — `POST /domains/{code}/compile`, `POST /domains/{code}/submit`.
- `app/main.py` — registers compilation router.
- `app/exceptions.py` — `ExternalServiceError` now accepts `code`.
- `app/services/notification_templates.py` — `domain_submitted` template (pre-existing, now covered by unit test).
- `tests/unit/test_compiler_crew.py` — unit tests for narrative generation and retry behavior.
- `tests/unit/test_services_compilation.py` — unit tests for compile/submit preconditions and notifications.
- `tests/unit/test_routers_compilation.py` — router auth and compile+submit flow tests.
- `tests/unit/conftest.py` — standalone unit-test app fixture including compilation router.
- `tests/steps/test_contributor_questionnaire.py` — added QSTN-02/03 step definitions and compiler fake fixture.
- `tests/steps/conftest.py` — mounts compilation router in BDD app fixture.
- `features/contributor-questionnaire.feature` — QSTN-02/03 scenarios.
- `frontend/e2e/compilation.spec.ts` — Playwright API smoke test for compile + submit.
- `frontend/playwright.config.ts` — starts dev backend with `LLM_PROVIDER=fake`.

## Known technical notes

- `compile_domain` checks that every enabled question is answered, not skipped, and followups_state is `complete` or `waived`. It raises `ExternalServiceError(llm_unavailable)` on LLM failure without changing domain state (C-19).
- `submit_domain` requires `submit_ready == True` and a compiled answer, then transitions the domain to `in_review` (C-12) and notifies the reviewer.
- BDD step functions are synchronous and use `sqlite3` for direct DB assertions, plus `TestClient` for HTTP.
- E2E tests run against `demo.localhost:8000` with `Host` header; the backend must be started with `LLM_PROVIDER=fake` for deterministic compilation.
- A flaky TOTP timing failure in `test_assn02` was observed once during full suite run but passed on rerun and in isolation; no regression caused by Task 14.

## Next task: Task 15

**Objective:** Review workflow (REVW-01..05) — reviewer approve, edit + RevisionCrew + direct approval, defer, self-review warning, all 14 approved completes WISP version.

**Key constraints:**
- Reviewer can approve, request revision, or defer.
- Direct approval by the same contributor is allowed with a warning (REVW-04).
- All 14 domains approved completes the WISP (REVW-05).

**Verification target:**
- REVW-01..05 green.
