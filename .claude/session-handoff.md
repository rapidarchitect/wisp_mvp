# Session Handoff — WISPGen

**Date:** 2026-07-13 04:30 UTC  
**Branch:** `task-09-domain-seeding`  
**Last completed task:** Task 09 (domain seeding crew and demo tenant)

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
| Task 09 | `task-09-domain-seeding` | committed (current branch) | SeederCrew generates 5-10 yes-no questions per domain, `seed-demo` CLI provisions and seeds demo tenant, LLM outage marks domains `pending_questions` gracefully (C-08, C-19, SEED-01..SEED-03) |

## Current verification

- `uv run pytest tests/ -q` → **all green**
- `uv run pytest tests/steps -q` → **all green**
- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q` → **3 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `TESTPLAN.md` statuses updated to **green** for SIGN-01..05, AUTH-01..07, USER-01..06, and SEED-01..03.

## Active files of note

- `app/crews/seeder_crew.py` — `SeederCrew.seed_domain()` generates JSON questions via LLM, validates 5-10 count, and falls back to `pending_questions` on failure.
- `app/services/seeding.py` — `seed_all_domains()` and `retry_domain_seed()` orchestration.
- `app/services/domain.py` — `get_domains_for_version()`, `get_questions_for_domain()`.
- `app/cli.py` — async `seed_demo()` command creates/provisions the `demo` tenant and seeds all 14 domains.
- `features/domain-seeding-and-questions.feature` — SEED-01..SEED-03 scenarios.
- `tests/steps/test_domain_seeding_and_questions.py` — step definitions for seeding, demo, and outage scenarios.
- `tests/steps/conftest.py` — shared `provisioned_tenant` fixture now fully provisions version 1 and 14 domains; shared admin/sign-in steps live here.

## Known technical notes

- BDD step functions are **synchronous** and use `sqlite3` for direct DB assertions, plus `fastapi.testclient.TestClient` for HTTP. This avoids pytest-bdd async step issues.
- `freezegun` is used for time-based scenarios.
- pytest-bdd emits `PytestRemovedIn10Warning` warnings about fixture scoping; these are non-failing library warnings.
- `fastapi.testclient` warns about `httpx` deprecation; also non-failing.
- The `provisioned_tenant` fixture now calls `app.services.provisioning.provision_tenant()` so every scenario starts with a complete tenant (control record, DB file, schema, version 1, 14 domains). Existing steps that previously inserted version/domain rows now tolerate pre-existing rows.
- All LLM/Tavily calls in the test suite use fakes; no real model or network is invoked.

## Next task: Task 10

**Objective:** Question management — admin custom questions, disabling seeded questions, and regeneration guardrails. Scenarios SEED-04..06.

**Files likely to create/modify (per master plan):**
- `app/services/questions.py`, `app/api/routers/questions.py`
- `tests/steps/test_domain_seeding_and_questions.py`
- Possibly extend `features/domain-seeding-and-questions.feature` (requires human approval per `AGENTS.md`).

**Key constraints:**
- C-08: exactly 14 domains, 5-10 enabled questions each.
- Regeneration only allowed when a domain is unanswered/unapproved.

**Verification target:**
- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "SEED-04 or SEED-05 or SEED-06"` green.
- Full BDD suite remains green.
