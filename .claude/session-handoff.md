# Session Handoff — WISPGen

**Date:** 2026-07-14  
**Branch:** `task-16-versioning-export`  
**Last completed task:** Task 16 (Versioning and PDF Export) — VERS-01..05 green, tests and lint clean.

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
| Task 14 | `task-14-compilation-submission` | committed on `main` | CompilerCrew, compilation/submission service, compile/submit endpoints, BDD QSTN-02/03 green, Playwright compile+submit smoke (C-12, C-19) |
| Task 15 | `task-15-review-workflow` | committed | RevisionCrew, review service, approve/revise/defer endpoints, REVW-01..05 green, notification templates for `domain_approved`, `domain_revised_and_approved`, `domain_deferred`, `wisp_complete`, Playwright review smoke |
| Task 16 | `task-16-versioning-export` | current branch | PDF export via fpdf2, version lifecycle service, version/export router, VERS-01..05 green (C-13, C-14, C-15) |

## Current verification

- `uv run pytest tests/ -q` → **155 passed, 1 skipped**
- `uv run pytest tests/steps -q` → **49 passed**
- `uv run pytest tests/steps/test_wisp_versioning_and_export.py -q` → **5 passed**
- `uv run pytest tests/unit -q` → **94 passed, 1 skipped**
- `uv run pytest --cov=app --cov-report=term-missing tests/unit -q` → **88.81% total**, `app/services` ≥85%
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `TESTPLAN.md` statuses updated: **VERS-01..05 green**.

## Active files of note

- `app/services/pdf.py` — `render_wisp_pdf()` using fpdf2; DRAFT watermark gated by `include_draft` (C-13).
- `app/services/versions.py` — `start_new_version`, `get_current_version`, `list_versions`; single-in-progress guard (C-14); clones approved domains/compiled answers/assignments to new version (C-15).
- `app/api/routers/versions.py` — `GET /versions`, `GET /versions/current/export`, `GET /versions/{number}/export`, `POST /versions`.
- `tests/unit/test_services_pdf.py`, `tests/unit/test_services_versions.py`, `tests/unit/test_routers_versions.py` — unit coverage.
- `tests/steps/test_wisp_versioning_and_export.py` — BDD step definitions for VERS-01..05.
- `features/wisp-versioning-and-export.feature` — VERS-01..05 scenarios.
- `pyproject.toml`/`uv.lock` — added `fpdf2` and `pdfminer.six` (dev).

## Known technical notes

- WeasyPrint was approved but could not import on macOS without system Pango libraries, so I switched to **fpdf2** with your approval. PDF text-layer assertions use `pdfminer.six`.
- `render_wisp_pdf` accepts an explicit `company_name` from the router because tenant company name lives in the control DB, not the tenant DB vitals table.
- `start_new_version` refuses to create a second version while any version is `in_progress` (C-14).
- Prior completed versions remain readable and exportable via `/versions/{number}/export` (C-15).
- Reviewer approve/revise/defer steps were moved to `tests/steps/common_steps.py` with both `@given` and `@when` decorators so they can be reused across `review-workflow` and `wisp-versioning-and-export` features.

## Next task: Task 17

**Objective:** React frontend: auth, onboarding, dashboards — E2E coverage of SIGN-01, AUTH-01, AUTH-02, USER-02.

**Key constraints:**
- Signup wizard collects corporate vitals per the field list.
- Login + TOTP screens.
- Role-aware dashboards with KPIs and progress.
- Generated API types from the running dev API.

**Verification target:**
- `npm run gen:api` against running dev API.
- `npm run test` and `npx playwright test frontend/e2e/signup.spec.ts frontend/e2e/auth.spec.ts frontend/e2e/users.spec.ts` green.
