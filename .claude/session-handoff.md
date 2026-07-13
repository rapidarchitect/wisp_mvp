# Session Handoff — WISPGen

**Date:** 2026-07-13 12:30 UTC  
**Branch:** `task-11-email-backends`  
**Last completed task:** Task 11 (Notifications)

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
| Task 11 | `task-11-email-backends` | committed (current branch) | Notifications service, in-app feed endpoint, console/SES email backends with singleton factory, `notify()` wired into invitations, role changes, and deactivation (Task 11 scenario-exempt) |

## Current verification

- `uv run pytest tests/ -q` → **all green**
- `uv run pytest tests/steps -q` → **all green**
- `uv run pytest tests/unit/test_services_notifications.py tests/unit/test_routers_notifications.py -q` → **all green**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `uv run pytest --cov=app/services --cov-report=term-missing tests/unit/test_services_notifications.py` → **93%+ coverage**
- `TESTPLAN.md` statuses updated: SIGN-01..05, AUTH-01..07, USER-01..06, SEED-01..06 green; Task 11 covered as cross-cutting notification service.

## Active files of note

- `app/services/notifications.py` — `notify()`, `get_notifications()`, `mark_read()`, dual-channel dispatch (in-app + email).
- `app/services/email_backends.py` — `ConsoleEmailBackend`, `SESEmailBackend`, singleton `get_email_backend()`, `reset_email_backend()` for tests.
- `app/api/routers/notifications.py` — `/notifications` feed and `/notifications/{id}/read` endpoints.
- `app/models/notification.py` — `NotificationCreate`, `NotificationOut`, `NotificationList`.
- `tests/unit/test_services_notifications.py` — unit tests for service, backends, SES error wrapping, singleton factory.
- `tests/unit/test_routers_notifications.py` — router-level feed/mark-read tests via `TestClient`.
- `app/services/invitations.py`, `app/services/users.py` — wired to call `notify()` on invite, role change, deactivation.
- `tests/steps/conftest.py` — mounts notifications router, clears captured console emails.

## Known technical notes

- BDD step functions are **synchronous** and use `sqlite3` for direct DB assertions, plus `TestClient` for HTTP.
- `get_email_backend()` caches the backend instance by type; `reset_email_backend()` clears the cache for tests and runtime backend switches.
- SES backend uses `boto3.client` and `asyncio.to_thread`; errors are wrapped as `ExternalServiceError`.
- All LLM/Tavily calls in the test suite use fakes; no real model or network is invoked.
- The `provisioned_tenant` fixture does **not** eagerly seed domains, preserving SEED-01..03 semantics.

## Next task: Task 12

**Objective:** Domain Assignment (ASSN-01..ASSN-05, C-10) — assign one contributor and one reviewer per domain, enforce single assignee per role, preserve answers on reassignment, restrict contributor visibility to assigned domains, and surface unassigned domains to admin.

**Files likely to create/modify (per master plan):**
- `app/services/domain_assignment.py`, `app/api/routers/domain_assignment.py`, `tests/unit/test_services_domain_assignment.py`
- Modify `app/db/schema/tenant.sql`, `app/main.py`, `features/domain-assignment.feature`, `tests/steps/test_domain_assignment.py`

**Key constraints:**
- Exactly one contributor and one reviewer per domain at any time.
- Reassignment updates assignments but preserves existing answers and compiled text.
- Contributors list only domains assigned to them; reviewers similarly.
- Admin dashboard endpoint lists domains with missing assignments.

**Verification target:**
- `uv run pytest tests/steps/test_domain_assignment.py -q` green.
- `uv run pytest tests/unit/test_services_domain_assignment.py -q` green.
- Coverage on `app/services` ≥ 85%.
