# Session Handoff — WISPGen

**Date:** 2026-07-14  
**Branch:** `task-15-review-workflow`  
**Last completed task:** Task 15 (Review Workflow) — BDD scenarios REVW-01..05 green, tests and lint clean.

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
| Task 15 | `task-15-review-workflow` | current branch | RevisionCrew, review service, approve/revise/defer endpoints, REVW-01..05 green, notification templates for `domain_approved`, `domain_revised_and_approved`, `domain_deferred`, `wisp_complete` |

## Current verification

- `uv run pytest tests/ -q` → **145 passed**
- `uv run pytest tests/steps -q` → **44 passed**
- `uv run pytest tests/steps/test_review_workflow.py -q` → **5 passed**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `TESTPLAN.md` statuses updated: **REVW-01..05 green**.

## Active files of note

- `app/crews/revision_crew.py` — deterministic fake LLM-friendly revision of a compiled narrative from a reviewer prompt.
- `app/services/review.py` — `approve_domain`, `revise_and_approve`, `defer_domain`, self-review warning, and `_maybe_complete_version`.
- `app/api/routers/review.py` — `POST /domains/{code}/approve`, `/revise`, `/defer`.
- `app/services/notification_templates.py` — added templates for review workflow notifications.
- `app/services/compilation.py` — `load_answered_questions` is now public for reuse by the revision service.
- `tests/unit/test_revision_crew.py`, `tests/unit/test_services_review.py`, `tests/unit/test_routers_review.py` — unit coverage.
- `tests/steps/test_review_workflow.py` — BDD step definitions for REVW-01..05.
- `tests/steps/common_steps.py` — shared notification assertions and assignment upsert; reused by questionnaire and review scenarios.
- `features/review-workflow.feature` — REVW-01..05 scenarios.

## Known technical notes

- `revise_and_approve` persists the AI-generated revision to `compiled_answers`, audits `domain_revised`, transitions the domain to `approved`, and sends `domain_revised_and_approved` to the contributor.
- `approve_domain` allows a reviewer who is also the contributor to approve, but returns `self_review: true` in the response.
- `_maybe_complete_version` checks whether every domain in the version is approved; if so it marks the version `complete` and notifies the admin.
- `given_domain_assigned` now uses `ON CONFLICT(domain_id) DO UPDATE` so scenarios can reassign the same domain for self-review tests.
- A flaky TOTP timing failure in `test_regeneration_only_when_unanswered_seed06` was observed once during a full suite run but passed on rerun and in isolation; no regression caused by Task 15.

## Next task: Task 16

**Objective:** WISP versioning and export (VERS-01..05) — draft watermark, clean final export, new version clones approved baseline, only one version in progress, prior versions remain exportable.

**Key constraints:**
- Draft/complete export behavior differs (VERS-01, VERS-02).
- New version starts from the approved baseline (VERS-03).
- Only one `in_progress` version per tenant (VERS-04).
- Prior versions remain exportable (VERS-05).

**Verification target:**
- VERS-01..05 green.
