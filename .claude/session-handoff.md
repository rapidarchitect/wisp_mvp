# Session Handoff — WISPGen

**Date:** 2026-07-15
**Branch:** `task-20-e2e-regression`
**Last completed task:** Task 20 (full Playwright E2E regression suite) — all 45 scenario IDs green in TESTPLAN.md.

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
| Task 18 | `task-18-contributor-reviewer-ui` | committed | Contributor questionnaire page, reviewer queue/review page, admin versions/export page; E2E QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02 green |
| Task 20 | `task-20-e2e-regression` | current branch | Full Playwright regression suite for all scenario IDs; test-only endpoints, fixtures, E2E stability fixes, lint clean |

## Current verification

- `uv run pytest tests/ -q` → **237 passed, 1 skipped**
- `uv run pytest tests/steps -q` → **49 passed**
- `uv run pytest tests/unit -q` → **188 passed, 1 skipped**
- `uv run ruff check . && uv run ruff format --check .` → **clean**
- `npm run build` → **clean** (chunk-size warning only)
- `DOCKER_DEV=1 npx playwright test` → **45 passed**
- `TESTPLAN.md` statuses updated: **all E2E rows green**.

## Active files of note

- `frontend/e2e/auth.spec.ts`, `signup.spec.ts`, `users.spec.ts`, `seeding.spec.ts`, `domain-assignment.spec.ts`, `questionnaire.spec.ts`, `review.spec.ts`, `versions.spec.ts` — full E2E coverage.
- `frontend/e2e/api.ts` — E2E helpers including `testLogin` to bypass TOTP in API setup.
- `frontend/e2e/fixtures.ts` — `resetAll` isolation fixture.
- `frontend/e2e/setup.py` — Docker dev stack baseline seeder.
- `app/api/routers/test.py` — test-only endpoints for reset, mode toggles, invitation/email introspection.
- `app/api/routers/users.py` — `GET /users/invitations` for admin pending-invitations UI.
- `app/services/answers.py` — domain progress returns `contributor_id`/`reviewer_id`.
- `app/services/auth.py` — password-only login returns `totp_required` for enrolled users.
- `app/services/users.py` — deactivation resets in-progress/ready domains to `pending_questions`.
- `frontend/src/pages/AdminUsersPage.tsx` — pending invitations list.
- `frontend/src/pages/LoginPage.tsx` — disables password autofill to prevent strict-mode violations.
- `frontend/src/pages/ReviewDomainPage.tsx` — self-review warning keyed to `contributor_id`.
- `frontend/src/auth/AuthContext.tsx` — distinguishes `totp_required` from invalid credentials.
- `frontend/playwright.config.ts` — single worker / non-parallel for Docker dev SQLite.

## Known technical notes

- `resetAll` rebuilds a single in-progress WISP version with 14 empty domains, deterministic seeded questions, resets the demo voucher, clears lockout state, deletes ad-hoc `e2e%` users, and resets service doubles.
- Backend `/test/login` bypasses TOTP to avoid clock-drift flakes during long API-driven E2E setup sequences.
- Workers are forced to 1 and `fullyParallel: false` under `DOCKER_DEV=1` to avoid SQLite contention.

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
