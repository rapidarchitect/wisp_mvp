# Session Handoff — WISPGen

**Date:** 2026-07-13 23:55 UTC  
**Branch:** `task-12-domain-assignment`  
**Last completed task:** Task 12 (Domain Assignment + E2E smoke tests)

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
| Task 12 | `task-12-domain-assignment` | committed (current branch) | Domain assignment service/router, exactly one contributor + one reviewer per domain, role-scoped visibility, admin gap flag, BDD scenarios ASSN-01..05 green, Playwright API smoke tests (C-10) |

## Current verification

- `uv run pytest tests/ -q` → **111 passed**
- `uv run pytest tests/steps -q` → **33 passed**
- `uv run pytest tests/unit/test_services_domain_assignment.py tests/unit/test_routers_domain_assignment.py -q` → **19 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `uv run pytest --cov=app/services --cov-report=term-missing tests/unit -q` → **88.44% ≥ 85%**
- `npm run test:e2e` (with backend/frontend running) → **7 passed**
- `TESTPLAN.md` statuses updated: SIGN-01..05, AUTH-01..07, USER-01..06, SEED-01..06, **ASSN-01..05 green**.

## Active files of note

- `app/services/domain_assignment.py` — `assign_domain`, `get_unassigned_domains`, `list_user_assignments`.
- `app/api/routers/domain_assignment.py` — `/domains/{code}/assign`, `/domains/unassigned`, `/domains/assigned`.
- `app/models/domain_assignment.py` — `AssignDomainRequest`.
- `tests/unit/test_services_domain_assignment.py` — unit tests for validation, replacement, audit, notifications, answer preservation.
- `tests/unit/test_routers_domain_assignment.py` — router auth/response tests.
- `tests/steps/test_domain_assignment.py` — BDD step definitions for ASSN-01..05.
- `tests/steps/common_steps.py` — shared cross-feature Givens.
- `features/domain-assignment.feature` — ASSN-01..05 scenarios.
- `frontend/e2e/domain-assignment.spec.ts` — Playwright API smoke tests for assignment.
- `frontend/e2e/setup.py` — seeds demo tenant + deterministic test users for e2e.
- `app/ai/llm_factory.py` — default Ollama model changed to `ollama/hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0`.

## Known technical notes

- BDD step functions are **synchronous** and use `sqlite3` for direct DB assertions, plus `TestClient` for HTTP.
- Cross-feature Givens live in `tests/steps/common_steps.py`; `tests/conftest.py` registers them via `pytest_plugins`.
- `tests/steps/helpers.py` holds shared step utilities like `_tenant_db_path`.
- Assignment audit event is written inside the immediate transaction; notifications are sent after commit so email failures do not roll back the assignment.
- E2E tests run against `demo.localhost:8000` with `Host` header; test users use `@demo.example.com` emails to satisfy Pydantic `EmailStr` while tenant resolution stays based on `Host`.

## Next task: Task 13

**Objective:** Contributor questionnaire flow (QSTN-01, QSTN-04, QSTN-05, QSTN-06, C-09, C-11, C-19) — answer capture, up to 3 AI follow-ups, skip behavior that blocks submission, save/resume, AI outage fallback.

**Files likely to create/modify (per master plan):**
- `app/crews/followup_crew.py`, `app/services/answers.py`, `app/services/followups.py`, `app/api/routers/questionnaire.py`
- `tests/unit/test_services_answers.py`, `tests/steps/test_contributor_questionnaire.py`
- Modify `features/contributor-questionnaire.feature` (requires explicit approval)

**Key constraints:**
- Each answer triggers up to 3 AI-generated follow-up questions.
- Skipped questions defer the answer but block final domain submission.
- Contributor can save progress and resume exactly.
- LLM outage falls back to plain answer without crashing (C-19).

**Verification target:**
- `uv run pytest tests/steps/test_contributor_questionnaire.py -q -k "QSTN-01 or QSTN-04 or QSTN-05 or QSTN-06"` green.
- Coverage on `app/services` ≥ 85%.
