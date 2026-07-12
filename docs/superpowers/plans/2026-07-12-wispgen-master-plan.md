# WISPGen Implementation Master Plan

> **Approved:** 2026-07-12  
> **For agentic workers:** Use `superpowers:subagent-driven-development` to execute task-by-task.

**Goal:** Build WISPGen from spec to a deployed, tested multi-tenant SaaS that generates Written Information Security Programs for small accounting firms.

**Architecture:** FastAPI backend with per-tenant SQLite files, React + Vite + TypeScript frontend, CrewAI crews behind an LLM factory, Stripe Checkout + webhook, SES email, Tavily research, Terraform/AWS deployment.

**Tech Stack:** Python 3.12, FastAPI, uv, aiosqlite, httpx, orjson, pydantic v2, argon2-cffi, pyotp, itsdangerous, crewai, boto3, stripe, weasyprint, tavily-python, pytest-bdd, ruff; React 18, TypeScript, Vite, Vitest, Playwright.

## Global Constraints

- `uv` only; `pip` is forbidden.
- No ORMs; raw parameterized SQL via `aiosqlite`.
- No Celery, queue brokers, `requests`, or CSS-in-JS.
- `httpx` only; `orjson` only.
- Feature files (`features/*.feature`) are spec. Do not create or edit without explicit human approval.
- `constitution.md` and constraints C-01 through C-19 are immutable.
- One task per branch: `task-NN-short-desc`.
- Every commit cites task number and constraint IDs: `feat(task-06): voucher redemption path (C-17)`.
- Tests never call real LLM, Tavily, Stripe, or SES endpoints.
- Tenant identity comes from the resolved subdomain only (C-01); never accept tenant ID from request input.
- Never log tenant answers, vitals, or TOTP secrets (C-18).
- Coverage minimum 85% on `app/services` and `app/domain`.

---

## Phase 0: Documentation Alignment (pre-Task 01)

**Objective:** Reconcile `AGENT.md` with `AGENTS.md`, capture the missing `features/` directory in a human-approval workflow, and create non-spec planning placeholders.

**Files:**
- Modify: `AGENT.md`, `AGENTS.md`
- Create: `docs/bdd/feature-index.md`, `docs/bdd/acceptance-criteria.md` (DRAFT), `features/README.md`

**Steps:**
1. Rewrite `AGENT.md` as an OpenCode bootstrap prompt, matching `AGENTS.md` reading order and current repo state.
2. Add to `AGENTS.md` Hard rules: "Do not create `features/*.feature` files without explicit human approval."
3. Create `docs/bdd/feature-index.md` as a Markdown table of the 8 feature files and 45 scenarios from `TESTPLAN.md`.
4. Draft `docs/bdd/acceptance-criteria.md` from `TESTPLAN.md` Section 5; mark `DRAFT — pending approval`.
5. Create `features/README.md` explaining the directory is a placeholder and `.feature` files require approval.
6. Submit documentation changes for approval; create the eight `.feature` files from the inventory before Task 03 begins.

**Verification:**
- `uv run ruff check . && uv run ruff format --check .` exits 0.
- `ls features/` shows only `README.md`.

---

## Phase 1: Backend Foundation

### Task 01: Repo Scaffold and Toolchain

**Objective:** Create the monorepo skeleton and wire backend/frontend toolchains so every command in `SPEC.md` Section 6 exits 0 on empty suites.

**Files:**
- Create: `pyproject.toml`, `.python-version`, `app/main.py`, `app/config.py`, `app/exceptions.py`, `app/cli.py`, `tests/conftest.py`, `tests/unit/test_config.py`, `tests/steps/conftest.py`, `tests/steps/common_steps.py`, `tests/steps/test_*.py` (8 feature step files), `frontend/` Vite scaffold, `infra/README.md`
- Modify: `README.md`

**Verification:**
- `uv sync` succeeds.
- `uv run pytest tests/ -q` exits 0.
- `uv run ruff check . && uv run ruff format --check .` exits 0.
- `uv run uvicorn app.main:app --reload` serves `/health`.
- `cd frontend && npm install && npm run dev`, `npm run build`, `npm run test`, `npx playwright test` all exit 0.

### Task 02: Tenancy Core

**Objective:** Control-plane DB, per-tenant SQLite factory, subdomain middleware enforcing C-01.

**Files:**
- Create: `app/db/control.py`, `app/db/tenant.py`, `app/db/schema/control.sql`, `app/db/schema/tenant.sql`, `app/middleware/tenancy.py`, `app/models/tenant.py`, `app/services/tenant.py`, `tests/unit/test_db_*.py`, `tests/unit/test_middleware_tenancy.py`
- Modify: `app/main.py`, `app/config.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `get_control_db()`, `init_control_db()`, `tenant_db_path()`, `init_tenant_db()`, `TenantMiddleware`, `resolve_subdomain()`, `get_tenant_by_slug()`, `create_tenant_record()`.

**Verification:**
- Unit tests prove two tenants never share a connection and unknown slug returns branded 404.
- `uv run pytest tests/unit/test_db_* tests/unit/test_middleware_tenancy.py -q` green.

### Task 03: Auth Core

**Objective:** Argon2id passwords, 12-char policy, 8-hour sessions, 5-failure lockout, audit log foundation. Scenarios: AUTH-03, AUTH-05, AUTH-06.

**Files:**
- Create: `app/models/auth.py`, `app/models/user.py`, `app/services/auth.py`, `app/services/audit.py`, `app/api/routers/auth.py`, `tests/unit/test_services_auth.py`, `tests/unit/test_services_audit.py`
- Modify: `app/db/schema/tenant.sql`, `app/main.py`, `tests/steps/test_authentication.py`

**Interfaces:**
- Produces: `hash_password()`, `verify_password()`, `validate_password()`, `create_session()`, `get_user_from_session()`, `record_failed_login()`, `is_account_locked()`, `audit()`.

**Verification:**
- `uv run pytest tests/steps/test_authentication.py -q -k "wrong password or lock after 5 or expired session"` green.
- freezegun-driven clocks; no real sleeps.

### Task 04: TOTP Enrollment and Login

**Objective:** Mandatory pyotp TOTP enrollment; every login requires password + TOTP. Scenarios: AUTH-01, AUTH-02, AUTH-04.

**Files:**
- Create: `app/services/totp.py`, `app/models/totp.py`, `tests/unit/test_services_totp.py`
- Modify: `app/services/auth.py`, `app/api/routers/auth.py`, `tests/steps/test_authentication.py`

**Interfaces:**
- Produces: `generate_totp_secret()`, `get_provisioning_uri()`, `verify_totp()`, `login()`.

**Verification:**
- `uv run pytest tests/steps/test_authentication.py -q` green.

### Task 05: Password Reset

**Objective:** Signed 30-minute reset tokens and email dispatch. Scenario: AUTH-07.

**Files:**
- Create: `app/services/password_reset.py`, `app/models/password_reset.py`, `app/services/email_backends.py`, `tests/unit/test_services_password_reset.py`
- Modify: `app/api/routers/auth.py`, `app/config.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `create_reset_token()`, `verify_reset_token()`, `reset_password()`, `ConsoleEmailBackend`.

**Verification:**
- `uv run pytest tests/steps/test_authentication.py -q -k "password reset"` green.

### Task 06: Signup, Vitals, Payment, Provisioning

**Objective:** Signup flow, vitals validation, slug derivation, Stripe Checkout, voucher redemption, tenant provisioning with version 1 and 14 domains. Scenarios: SIGN-01..05.

**Files:**
- Create: `app/models/signup.py`, `app/models/corporate_vitals.py`, `app/models/subscription.py`, `app/models/voucher.py`, `app/models/domain.py`, `app/models/version.py`, `app/services/signup.py`, `app/services/payment.py`, `app/services/provisioning.py`, `app/api/routers/signup.py`, tests
- Modify: `app/db/control.py`, `app/db/tenant.py`, `app/main.py`, `tests/steps/test_signup_and_onboarding.py`

**Interfaces:**
- Produces: `validate_corporate_vitals()`, `derive_slug()`, `create_tenant()`, `create_checkout_session()`, `handle_checkout_webhook()`, `redeem_voucher()`, `provision_tenant()`, `create_initial_version()`, `create_14_domains()`.

**Verification:**
- `uv run pytest tests/steps/test_signup_and_onboarding.py -q` green.
- Declined card leaves no tenant DB file.

### Task 07: Invitations, Roles, Deactivation

**Objective:** 7-day invite tokens, activation with password + TOTP, multi-role grants, duplicate-invite rejection, deactivation flags domains while preserving answers. Scenarios: USER-01..06.

**Files:**
- Create: `app/models/invitation.py`, `app/services/invitations.py`, `app/services/users.py`, `app/api/routers/users.py`, tests
- Modify: `app/db/schema/tenant.sql`, `app/main.py`, `tests/steps/test_user_and_role_management.py`

**Interfaces:**
- Produces: `invite_user()`, `accept_invitation()`, `set_roles()`, `deactivate_user()`, `list_users()`.

**Verification:**
- `uv run pytest tests/steps/test_user_and_role_management.py -q` green.

### Task 11: Notifications (in-app + SES)

**Objective:** Single `notify()` service used by all workflows; in-app feed endpoint; console backend in dev/test, SES in prod.

**Files:**
- Create: `app/models/notification.py`, `app/services/notifications.py`, `app/api/routers/notifications.py`, `tests/unit/test_services_notifications.py`
- Modify: `app/db/schema/tenant.sql`, `app/main.py`, `app/config.py`, `tests/conftest.py`, `tests/steps/common_steps.py`

**Interfaces:**
- Produces: `notify()`, `get_notifications()`, `mark_read()`, `SESEmailBackend`.

**Verification:**
- `uv run pytest tests/unit/test_services_notifications.py -q` green.
- Coverage on `app/services` ≥ 85%.

---

## Phase 2: AI Workflow

### Pre-phase Contract

Before Task 08, lock these contracts in `docs/generated/phase2-contracts.md`:
- Pydantic models for `Domain`, `Question`, `Answer`, `FollowUp`, `CompiledAnswer`, `DomainAssignment`, `WISPVersion`, `Notification`, `AuditEvent`.
- `TenantDB` handle and repository helpers.
- `notify(db, user_id, kind, payload)` and `audit(db, actor, event, subject, detail=None)` signatures.
- `WISPGEN_ENV` and `LLM_PROVIDER` env contract.

### Task 08: LLM Factory, CrewAI Base, Tavily Tool

**Objective:** Configurable LLM factory, reusable crew base with one-retry exponential backoff, Tavily tool wrapper, deterministic test doubles.

**Files:**
- Create: `app/ai/llm_factory.py`, `app/ai/crew_base.py`, `app/ai/tavily_tool.py`, `app/ai/fakes.py`, `tests/unit/test_llm_factory.py`, `tests/unit/test_crew_base.py`, `tests/unit/test_tavily_tool.py`
- Modify: `app/config.py`, `tests/steps/conftest.py`

**Interfaces:**
- Produces: `create_llm()`, `CrewBase.run_with_retry()`, `TavilySearchTool`, `FakeLLM`, `FakeTavilySearchTool`.

**Verification:**
- Unit tests cover provider selection, retry, failure surfacing, and fake doubles.

### Task 09: Domain Seeding Crew and Demo Tenant

**Objective:** SeederCrew produces 5–10 yes-no questions per domain; fan-out across 14 domains; graceful outage handling; `seed-demo` CLI. Scenarios: SEED-01..03.

**Files:**
- Create: `app/crews/seeder_crew.py`, `app/services/seeding.py`, `app/services/domain.py`, tests
- Modify: `app/services/provisioning.py`, `app/cli.py`, `tests/steps/test_domain_seeding_and_questions.py`

**Interfaces:**
- Produces: `SeederCrew.seed_domain()`, `seed_all_domains()`, `retry_domain_seed()`.

**Verification:**
- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "SEED-01 or SEED-02 or SEED-03"` green.
- `uv run python -m app.cli seed-demo` seeds 14 domains.

### Task 10: Question Management

**Objective:** Admin add/edit/disable/reinstate questions; regeneration only when unanswered (C-16). Scenarios: SEED-04..06.

**Files:**
- Create: `app/services/questions.py`, `app/api/routers/questions.py`, `tests/unit/test_questions_service.py`
- Modify: `tests/steps/test_domain_seeding_and_questions.py`

**Interfaces:**
- Produces: `add_question()`, `edit_question()`, `disable_question()`, `reinstate_question()`, `regenerate_domain_questions()`.

**Verification:**
- `uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "SEED-04 or SEED-05 or SEED-06"` green.

### Task 12: Domain Assignment

**Objective:** Exactly one contributor and one reviewer per domain (C-10); replacement with notification; answer preservation; admin gap flagging. Scenarios: ASSN-01..05.

**Files:**
- Create: `app/services/assignment.py`, `app/api/routers/assignment.py`, `tests/unit/test_assignment_service.py`
- Modify: `app/db/schema/tenant.sql`, `tests/steps/test_domain_assignment.py`

**Interfaces:**
- Produces: `assign_domain()`, `get_unassigned_domains()`, `list_domains_for_user()`.

**Verification:**
- `uv run pytest tests/steps/test_domain_assignment.py -q` green.

### Task 13: Questionnaire Flow

**Objective:** Answer capture, FollowUpCrew (cap 3, C-09), skip blocks submission (C-11), save/resume, AI outage waiver (C-19). Scenarios: QSTN-01, QSTN-04, QSTN-05, QSTN-06.

**Files:**
- Create: `app/crews/followup_crew.py`, `app/services/answers.py`, `app/services/followups.py`, `app/api/routers/questionnaire.py`, tests
- Modify: `tests/steps/test_contributor_questionnaire.py`

**Interfaces:**
- Produces: `save_answer()`, `skip_question()`, `request_followups()`.

**Verification:**
- `uv run pytest tests/steps/test_contributor_questionnaire.py -q -k "QSTN-01 or QSTN-04 or QSTN-05 or QSTN-06"` green.

### Task 14: Compilation and Submission

**Objective:** CompilerCrew narrative generation, contributor preview, submission to `in_review` with contributor lock (C-12). Scenarios: QSTN-02, QSTN-03.

**Files:**
- Create: `app/crews/compiler_crew.py`, `app/services/compilation.py`, `app/api/routers/compilation.py`, tests
- Modify: `tests/steps/test_contributor_questionnaire.py`

**Interfaces:**
- Produces: `compile_domain()`, `submit_domain_for_review()`.

**Verification:**
- `uv run pytest tests/steps/test_contributor_questionnaire.py -q -k "QSTN-02 or QSTN-03"` green.

### Task 15: Review Workflow

**Objective:** Approve, defer, edit + RevisionCrew + direct approval, self-review warning, all-approved completes WISP. Scenarios: REVW-01..05.

**Files:**
- Create: `app/crews/revision_crew.py`, `app/services/review.py`, `app/api/routers/review.py`, tests
- Modify: `tests/steps/test_review_workflow.py`

**Interfaces:**
- Produces: `approve_domain()`, `defer_domain()`, `edit_and_approve_domain()`, `complete_wisp_version()`.

**Verification:**
- `uv run pytest tests/steps/test_review_workflow.py -q` green.

### Task 16: Versioning and PDF Export

**Objective:** WeasyPrint PDF with vitals/logo; DRAFT watermark gate (C-13); clone-forward new version; single in-progress guard (C-14); immutable prior versions (C-15). Scenarios: VERS-01..05.

**Files:**
- Create: `app/services/pdf.py`, `app/services/versions.py`, `app/templates/wisp.html`, `app/api/routers/versions.py`, tests
- Modify: `tests/steps/test_wisp_versioning_and_export.py`

**Interfaces:**
- Produces: `render_wisp_pdf()`, `start_new_version()`, `get_version()`, `list_versions()`.

**Verification:**
- `uv run pytest tests/steps/test_wisp_versioning_and_export.py -q` green.
- PDF text-layer tests assert `DRAFT` presence/absence by approval state.

---

## Phase 3: Frontend

### Task 17: Auth, Onboarding, Dashboards

**Objective:** Signup wizard, login + TOTP screens, role-aware dashboards. E2E: SIGN-01, AUTH-01, AUTH-02, USER-02.

**Files:**
- Create: `frontend/src/styles/index.css`, `frontend/src/styles/tokens.ts`, `frontend/src/api/client.ts`, `frontend/src/api/types.ts` (generated), `frontend/src/components/ui/*`, `frontend/src/components/layout/*`, `frontend/src/context/AuthContext.tsx`, `frontend/src/hooks/useAuth.ts`, `frontend/src/hooks/useTenant.ts`, `frontend/src/hooks/useDashboard.ts`, `frontend/src/router/Router.tsx`, `frontend/src/pages/SignupPage.tsx`, `frontend/src/pages/SignupPaymentPage.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/TotpEnrollPage.tsx`, `frontend/src/pages/TotpVerifyPage.tsx`, `frontend/src/pages/InvitationActivatePage.tsx`, `frontend/src/pages/DashboardPage.tsx`, `frontend/e2e/signup.spec.ts`, `frontend/e2e/auth.spec.ts`, `frontend/e2e/users.spec.ts`
- Modify: `frontend/src/main.tsx`, `frontend/package.json`

**Verification:**
- `npm run gen:api` against running dev API.
- `npm run test` and `npx playwright test frontend/e2e/signup.spec.ts frontend/e2e/auth.spec.ts frontend/e2e/users.spec.ts` green.

### Task 18: Questionnaire, Review, Export, Versions

**Objective:** Contributor questionnaire, reviewer screens, export controls, version history. E2E: QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02.

**Files:**
- Create: `frontend/src/components/domain/*`, `frontend/src/components/questionnaire/*`, `frontend/src/components/review/*`, `frontend/src/components/export/*`, `frontend/src/components/versions/*`, `frontend/src/hooks/useDomains.ts`, `frontend/src/hooks/useDomain.ts`, `frontend/src/hooks/useAnswer.ts`, `frontend/src/hooks/useReview.ts`, `frontend/src/hooks/useExport.ts`, `frontend/src/hooks/useVersions.ts`, `frontend/src/pages/DomainsPage.tsx`, `frontend/src/pages/QuestionnairePage.tsx`, `frontend/src/pages/ReviewPage.tsx`, `frontend/src/pages/ExportPage.tsx`, `frontend/src/pages/VersionsPage.tsx`, `frontend/e2e/questionnaire.spec.ts`, `frontend/e2e/review.spec.ts`, `frontend/e2e/export.spec.ts`
- Modify: `frontend/src/router/Router.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/pages/DashboardPage.tsx`

**Verification:**
- `npx playwright test frontend/e2e/questionnaire.spec.ts frontend/e2e/review.spec.ts frontend/e2e/export.spec.ts` green.

---

## Phase 4: Infra and E2E Regression

### Task 19: Terraform, nginx, certbot, Deployment

**Objective:** Single encrypted EC2 host, wildcard TLS for `*.app.wisp.llc`, nginx serving React + proxying FastAPI, systemd unit, deploy script.

**Files:**
- Create: `infra/provider.tf`, `infra/variables.tf`, `infra/main.tf`, `infra/outputs.tf`, `infra/userdata.sh`, `infra/files/nginx-wispgen.conf`, `infra/files/wispgen.service`, `infra/files/env.template`, `infra/files/wispgen-backup.sh`, `scripts/deploy.sh`, `.github/workflows/ci.yml`, `infra/README.md`
- Modify: `README.md`, `TESTPLAN.md` Section 8

**Verification:**
- `cd infra && terraform plan` clean.
- `curl -fsSI https://demo.app.wisp.llc/` returns 200 with HSTS.
- Wildcard cert shows `DNS:*.app.wisp.llc`.
- Manual checks recorded in `infra/README.md`: EBS encrypted, SG rules, wildcard cert.

### Task 20: Full Playwright Regression Suite

**Objective:** Browser-level specs covering every feature; `npx playwright test` green; TESTPLAN E2E column has no gaps.

**Files:**
- Create: `frontend/e2e/fixtures.ts`, `frontend/e2e/helpers.ts`, `frontend/e2e/*.spec.ts` (8 files)
- Modify: `frontend/playwright.config.ts`, `frontend/package.json`, `TESTPLAN.md` Section 4

**Verification:**
- `npx playwright test` exits 0.
- Every scenario ID from SIGN-01 through VERS-05 has a corresponding E2E row marked green.

---

## Parallel Execution Map

| Phase | Tasks | Can run in parallel |
|---|---|---|
| 0 | 0.1, 0.2 | Sequential |
| 1 | 01 → 02 → 03 → 04 | Task 05 and Task 07 parallel after Task 04; Task 11 parallel with 05/07 |
| 2 | 08 after 01; 09 after 02+08; 10 after 09; 12 after 07+09; 13 after 08+12; 14 after 08+13; 15 after 14; 16 after 15 | Task 10 parallel with Task 12 after Task 09 |
| 3 | 17 after 06+07; 18 after 13+14+15+16+17 | — |
| 4 | 19 after 01+06; 20 after 17+18 | Task 19 planning can start during Phase 2 |

## Cross-Cutting Verification

After every task:
1. `uv run pytest tests/ -q` green.
2. `uv run pytest tests/steps -q` green (full BDD suite).
3. `uv run ruff check . && uv run ruff format --check .` clean.
4. `uv run pytest --cov=app --cov-report=term-missing` ≥ 85% on `app/services` and `app/domain`.
5. Update `TESTPLAN.md` Section 4 status for the task's scenarios.
6. Commit message cites task and constraint IDs.
