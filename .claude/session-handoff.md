# Session Handoff — WISPGen

**Date:** 2026-07-14
**Branch:** `task-18-contributor-reviewer-ui`
**Last completed task:** Task 18 (React Contributor/Reviewer UI) — QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02 E2E green; tests and lint clean.

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
| Task 16 | `task-16-versioning-export` | committed | PDF export via fpdf2, version lifecycle service, version/export router, VERS-01..05 green (C-13, C-14, C-15) |
| Task 17 | `task-17-frontend-auth-dashboards` | committed | React auth, onboarding, dashboards; E2E SIGN-01, AUTH-01, AUTH-02, USER-02 green |
| Task 18 | `task-18-contributor-reviewer-ui` | current branch | Contributor questionnaire page, reviewer queue/review page, admin versions/export page; E2E QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02 green |

## Current verification

- `uv run pytest tests/ -q` → **237 passed, 1 skipped**
- `uv run pytest tests/steps -q` → **49 passed**
- `uv run pytest tests/unit -q` → **188 passed, 1 skipped**
- `uv run ruff check .` → **clean**
- `npm run build` → **clean** (chunk-size warning only)
- `npx playwright test e2e/questionnaire.spec.ts e2e/review.spec.ts e2e/versions.spec.ts` → **5 passed**
- `TESTPLAN.md` statuses updated: **QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02 E2E rows green**.

## Active files of note

- `frontend/src/pages/ContributorDomainsPage.tsx` — contributor's assigned domain list.
- `frontend/src/pages/DomainQuestionnairePage.tsx` — answer questions, follow-ups, compile, submit.
- `frontend/src/pages/ReviewerDomainsPage.tsx` — review queue for reviewer.
- `frontend/src/pages/ReviewDomainPage.tsx` — approve, defer, or revise-and-approve a domain.
- `frontend/src/pages/AdminVersionsPage.tsx` — version list and PDF export.
- `frontend/e2e/questionnaire.spec.ts` — QSTN-01, QSTN-02 E2E.
- `frontend/e2e/review.spec.ts` — REVW-01, REVW-02 E2E.
- `frontend/e2e/versions.spec.ts` — VERS-01, VERS-02 E2E.
- `frontend/e2e/api.ts` — `loginAsApi` helper for JWT seeding via API.
- `app/api/routers/test.py` — test-only reset/list endpoints for E2E isolation.
- `app/services/answers.py` — reviewer allowed to read domain progress; fixed `sqlite3.Row` dict access.
- `app/ai/fakes.py` — `FakeLLM` preserves explicit `default` and provides deterministic E2E fallbacks.
- `frontend/e2e/setup.py` — idempotent demo seed with answer/assignment reset.

## Known technical notes

- E2E tests now log in via API and set `wispgen_token` in `localStorage` to avoid TOTP clock drift during long setup sequences.
- VERS-02 E2E resets, assigns, submits, and approves all 14 domains via API to drive the version status to `complete`.
- Test-only endpoints are gated by `settings.enable_test_endpoints` (enabled in Playwright config via `WISP_ENV=test`).

## Next task: Task 19

**Objective:** Production infrastructure — Terraform, nginx, certbot, Docker, AWS deployment.

**Key constraints:**
- Infrastructure as code in `infra/`.
- Docker multi-stage build for the backend.
- nginx reverse proxy with Let's Encrypt (certbot).
- AWS ECS/Fargate or EC2 deployment path.

**Verification target:**
- `docker build -t wispgen -f infra/Dockerfile .` succeeds.
- `terraform plan` from `infra/terraform/` succeeds (dry-run).
