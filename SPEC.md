# SPEC: WISPGen

## 1. Objective

WISPGen is a multi-tenant SaaS that guides small accounting and tax firms through building a Written Information Security Program (WISP) satisfying IRS Publication 4557 and FTC Safeguards Rule expectations. AI-seeded questionnaires across 14 NIST-style security domains, AI follow-up interviews, and a contributor–reviewer workflow produce an exportable, versioned WISP PDF. Each firm gets an isolated workspace at `<company>.app.wisp.llc`.

## 2. Non-Goals

This project does NOT include:

1. **Compliance monitoring or verification** — no scanning of O365, Google Workspace, or any live environment to check that reality matches the WISP. That is the planned post-MVP tier; MVP is document generation only.
2. **Multiple subscription tiers, seat-based pricing, metered billing, refunds, or dunning** — one flat tier, Stripe Checkout or a 100% voucher, nothing else.
3. **SSO, SAML, OAuth social login, or WebAuthn** — authentication is email + password (Argon2id) + TOTP only.
4. **Native mobile apps or offline mode** — responsive web only.
5. **Horizontal scaling, Postgres migration, container orchestration, or multi-region** — one EC2 instance, nginx, per-tenant SQLite files. Do not introduce Docker, RDS, or a queue broker.
6. **In-app document editor for the exported PDF** — the WISP is generated from approved answers; there is no free-form WYSIWYG editing of the final document.
7. **Custom domain support per tenant** — subdomains of app.wisp.llc only.
8. **Internationalization** — English, US locale.

## 3. System Spec (Structured)

```yaml
system: WISPGen
entities:
  Tenant:
    fields: [id, slug (subdomain, unique), company_name, address, logo_path, status (provisioning|active|suspended), created_at]
    store: control-plane DB
  Subscription:
    fields: [id, tenant_id, tier (standard), funding (card|voucher), stripe_customer_id?, stripe_checkout_id?, voucher_code?, status (active|canceled), started_at]
    store: control-plane DB
  Voucher:
    fields: [code (unique), issued_to, redeemed_by_tenant_id?, redeemed_at?, expires_at]
    store: control-plane DB
  CorporateVitals:
    fields: [tenant_id, employee_range, clients_per_year_range, primary_software, deployment_type, has_efin (bool), it_support_provider, remote_access (bool), paper_files (bool), sensitive_data_types (set), coordinator_name, coordinator_title]
    store: tenant DB
  User:
    fields: [id, email (unique per tenant), password_hash (Argon2id), totp_secret?, totp_enrolled (bool), roles (set: admin|contributor|reviewer), status (invited|active|deactivated), failed_attempts, locked_until?, created_at]
    store: tenant DB
  Invitation:
    fields: [id, email, roles, token, expires_at (issued + 7 days), accepted_at?]
    store: tenant DB
  Session:
    fields: [id, user_id, issued_at, expires_at (issued + 8 hours)]
    store: tenant DB
  Domain:
    fields: [id, code (AC|PE|RA|CA|SC|SI|AT|AU|CM|IA|IR|MA|MP|PS), name, wisp_version_id, status (pending_questions|ready|assigned|in_progress|in_review|approved)]
    note: exactly 14 per WISP version
  Question:
    fields: [id, domain_id, text, answer_type (yes_no), origin (seeded|admin), enabled (bool), position]
  Answer:
    fields: [id, question_id, contributor_id, value (yes|no), skipped (bool), followups_state (pending|complete|waived), answered_at]
  FollowUp:
    fields: [id, answer_id, text, response_text?, position (1..3)]
  CompiledAnswer:
    fields: [id, domain_id, narrative_text, compiled_at, revised_by_reviewer_id?, approved_at?]
  DomainAssignment:
    fields: [domain_id, contributor_id (exactly one), reviewer_id (exactly one), assigned_at]
  WISPVersion:
    fields: [id, tenant_id, number, status (in_progress|complete), created_at, completed_at?, parent_version_id?]
  Notification:
    fields: [id, user_id, type, payload, channel (in_app|email|both), read_at?, sent_at]
  AuditEvent:
    fields: [id, actor_user_id?, event_type, subject, detail, at]
    note: all auth events recorded; no answer content in payloads

capabilities:
  signup_firm:            {actor: visitor, pre: subdomain available + vitals valid, post: Tenant provisioning, err: [slug_taken, vitals_invalid]}
  process_payment:        {actor: visitor, pre: signup complete, post: Subscription active (Stripe Checkout or voucher), err: [card_declined, voucher_invalid]}
  provision_tenant:       {actor: system, pre: payment confirmed, post: tenant SQLite created, 14 domains created, seeding queued}
  seed_domain_questions:  {actor: CrewAI+Tavily, pre: domain pending_questions, post: 5-10 yes-no questions per domain by industry+locale, err: [research_unavailable -> retryable]}
  invite_user:            {actor: admin, pre: email not active member, post: Invitation (7-day token), notification sent}
  activate_account:       {actor: invitee, pre: valid unexpired token, post: password set + TOTP enrolled + status active}
  manage_roles:           {actor: admin, post: user role set updated (multi-role allowed)}
  deactivate_user:        {actor: admin, post: sign-in blocked, assigned domains flagged for reassignment, answers preserved}
  login:                  {actor: any user, pre: not locked, post: session (8h) after password + TOTP, err: [invalid_credentials, invalid_totp, locked]}
  reset_password:         {actor: user, pre: emailed link < 30 min old, post: new password (>= 12 chars)}
  manage_questions:       {actor: admin, post: add|edit|disable|reinstate question}
  regenerate_questions:   {actor: admin, pre: domain has zero answers, post: fresh 5-10 questions, err: [domain_has_answers]}
  assign_domain:          {actor: admin, post: exactly one contributor + one reviewer; reassignment preserves answers + notifies displaced user}
  answer_question:        {actor: contributor, pre: domain assigned + not in_review, post: answer saved, followups requested (cap 3)}
  generate_followups:     {actor: CrewAI (Tavily-assisted), pre: answer saved, post: 0-3 followups, err: [llm_unavailable -> retry once -> waive with notice]}
  skip_question:          {actor: contributor, post: question deferred; domain not submittable while any skip outstanding}
  compile_domain:         {actor: CrewAI, pre: all questions answered + followups complete or waived, post: CompiledAnswer narrative}
  submit_domain:          {actor: contributor, pre: compiled answer exists, post: status in_review, domain locked for contributor, reviewer notified}
  review_approve:         {actor: reviewer, pre: domain in_review, post: approved, contributor notified; self-review shows warning}
  review_edit:            {actor: reviewer, pre: domain in_review, post: AI-revised CompiledAnswer; reviewer approves directly; contributor notified}
  export_wisp_pdf:        {actor: admin, post: PDF with vitals + logo + compiled answers; DRAFT watermark on every page unless all 14 domains approved}
  start_new_version:      {actor: admin, pre: no version in_progress, post: new version cloning prior approved answers; prior version read-only, err: [version_in_progress]}
  notify:                 {actor: system, post: in-app notification + SES email}
  audit:                  {actor: system, post: AuditEvent row for every auth and review event}

actors:
  CompanyAdmin: [signup_firm, invite_user, manage_roles, deactivate_user, manage_questions, regenerate_questions, assign_domain, export_wisp_pdf, start_new_version]
  Contributor:  [answer_question, skip_question, compile_domain, submit_domain]
  Reviewer:     [review_approve, review_edit]
  note: one user may hold any combination of roles
  SeederCrew:   {type: machine, tools: [Tavily], task: seed_domain_questions}
  FollowUpCrew: {type: machine, tools: [Tavily], task: generate_followups}
  CompilerCrew: {type: machine, task: compile_domain}
  RevisionCrew: {type: machine, task: review_edit revision}
  Stripe:       {type: machine, task: checkout + webhook confirmation}
  SES:          {type: machine, task: email delivery}

events:
  - PaymentConfirmed -> provision_tenant
  - TenantProvisioned -> seed all 14 domains
  - DomainSeedFailed -> domain shows "Questions pending", per-domain retry available
  - AnswerSaved -> generate_followups
  - FollowupsFailed(after retry) -> question complete without followups + contributor notice
  - DomainSubmitted -> reviewer notification (in-app + email)
  - DomainApproved -> contributor notification; if all 14 approved -> WISPComplete
  - WISPComplete -> version status complete + admin notification
  - AnswerEditedAndApproved -> contributor notification
  - DomainReassigned -> displaced user notification
  - UserDeactivated -> domains flagged for reassignment

constraints:
  C-01: {rule: one SQLite file per tenant; no request may touch another tenant's DB, source: tenancy decision}
  C-02: {rule: account locks 15 minutes after 5 failed attempts; password and TOTP failures both count, source: AUTH-04, AUTH-05}
  C-03: {rule: sessions expire 8 hours after sign-in; expiry never loses saved answers, source: AUTH-02, AUTH-06}
  C-04: {rule: TOTP enrollment mandatory at first login; every login requires password + current TOTP, source: AUTH-01}
  C-05: {rule: passwords hashed with Argon2id; minimum length 12, source: AUTH-07 [ASSUMED length]}
  C-06: {rule: password reset links expire after 30 minutes, source: AUTH-07}
  C-07: {rule: invitation links expire after 7 days, source: USER-05}
  C-08: {rule: exactly 14 domains; each seeded with 5-10 yes-no questions tailored to industry and locale, source: SEED-01}
  C-09: {rule: at most 3 AI follow-ups per initial question, source: QSTN-01}
  C-10: {rule: exactly one Contributor and one Reviewer per domain at a time; reassignment preserves answers, source: ASSN-02, ASSN-03}
  C-11: {rule: skipped questions block domain submission, source: QSTN-04}
  C-12: {rule: domain is read-only for the Contributor while in review, source: QSTN-03}
  C-13: {rule: PDF export carries DRAFT watermark on every page unless all 14 domains approved, source: VERS-01, VERS-02}
  C-14: {rule: at most one WISP version in progress per tenant, source: VERS-04}
  C-15: {rule: completed versions are immutable and remain exportable, source: VERS-03, VERS-05}
  C-16: {rule: question regeneration allowed only for domains with zero answers, source: SEED-06}
  C-17: {rule: a valid voucher fully replaces card payment, source: SIGN-02}
  C-18: {rule: no tenant answer content or vitals in application logs, source: cross-cutting AC [ASSUMED]}
  C-19: {rule: AI outage after one retry degrades gracefully (waived followups, pending seeds) — never blocks the user, source: QSTN-06, SEED-03}

integrations:
  Stripe:  {direction: outbound + webhook inbound, mode: Checkout session; webhook confirms payment}
  Tavily:  {direction: outbound, mode: CrewAI tool for question research and followup research}
  LLM:     {direction: outbound, mode: configurable factory — dev: Ollama hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0, prod: Bedrock kimi-2.5}
  SES:     {direction: outbound, mode: transactional email (invites, notifications, password reset)}

environment:
  hosting: single EC2 instance (t3.large [ASSUMED]), Ubuntu, EBS encrypted at rest
  web: nginx wildcard vhost *.app.wisp.llc -> FastAPI (uvicorn); React static build served by nginx
  tls: certbot wildcard cert via DNS-01 (Route 53 plugin)
  dns: wildcard A record *.app.wisp.llc -> elastic IP
  data: /srv/wispgen/data/control.db + /srv/wispgen/data/tenants/<slug>.db
  iac: Terraform — new SSH keypair, 443 open to world, 22 restricted to 24.11.224.55/32, elastic IP, AWS personal profile from ~/.aws
  security_note: SSH IP allowlist for a single home IP will break when the ISP rotates the address; document the terraform variable to update it

non_functional:
  security: [Argon2id, mandatory TOTP, audit log for auth + review events, EBS encryption, no tenant data in logs, secrets via environment file not committed]
  performance: [light concurrent load; SQLite WAL mode; per-tenant write serialization acceptable]
  reliability: [AI calls async with retry (1 retry, exponential backoff); Stripe webhook idempotent]
  compliance_context: [product output targets IRS Pub 4557 + FTC Safeguards Rule expectations; the app itself must model good practice]

open_questions:
  OQ-1: {q: Stripe webhook vs synchronous confirmation on redirect, default: webhook is source of truth + redirect optimistic UI, impact: medium}
  OQ-2: {q: PDF engine, default: WeasyPrint from HTML template, impact: low}
  OQ-3: {q: EC2 size, default: t3.large (Ollama runs only in dev, not on the instance), impact: low}
  OQ-4: {q: demo tenant reset policy, default: recreated on deploy, impact: low}
```

## 4. System Description (Narrative)

### Overview

WISPGen turns a regulatory obligation most small firms handle badly — writing and maintaining a WISP — into a guided interview. A firm signs up, describes itself through structured corporate vitals, and pays via Stripe Checkout or a voucher. The system provisions an isolated workspace on its own subdomain with its own SQLite database file, then uses a CrewAI research crew with Tavily search to seed 14 NIST-style security domains with 5 to 10 industry- and locale-appropriate Yes-No questions each.

Work is divided by role. The Company Admin assigns each domain to exactly one Contributor and one Reviewer (one person may hold all roles in a small firm). Contributors answer questions; each answer triggers up to three AI follow-ups; a compiler crew rewrites the full domain conversation into a single narrative answer. Reviewers approve or edit; edits are AI-revised and approved directly by the reviewer with the contributor notified. When all 14 domains are approved the WISP version is complete and exports as a clean PDF; before that, every export carries a DRAFT watermark.

Versions are clone-forward: a new version starts from the prior version's approved answers, exactly one version may be in progress, and completed versions are immutable but remain exportable. This gives firms an auditable annual-review trail, which is precisely what an IRS or FTC examiner asks for.

### Entities

The control-plane database holds only what must exist before a tenant database does: Tenant, Subscription, Voucher. Everything firm-specific — users, vitals, domains, questions, answers, versions, notifications, audit events — lives in the tenant's own SQLite file. This makes tenant isolation a filesystem property rather than a WHERE-clause discipline, and makes per-tenant backup a file copy.

Answer state is deliberately granular: an Answer records the Yes-No value and a followups_state of pending, complete, or waived; FollowUp rows hang off it with a position capped at 3 (C-09). The waived state is what makes AI outages non-blocking (C-19). CompiledAnswer is a separate entity because it has its own lifecycle — compiled, optionally reviewer-revised, approved — and because prior versions must freeze it immutably (C-15).

WISPVersion owns the 14 Domain rows for that version. Cloning a version copies domains, questions, and compiled answers as editable starting points while resetting statuses, and stamps the parent_version_id for the audit trail.

### Capabilities

Capabilities map one-to-one onto the approved Gherkin scenarios: every When step in the feature set corresponds to a capability above, every Given to entity state, every Then to postconditions or events. The four CrewAI crews — Seeder, FollowUp, Compiler, Revision — are modeled as machine actors with explicit error behavior, because their failure modes are user-visible scenarios (SEED-03, QSTN-06), not internal details.

Payment is intentionally thin: create a Stripe Checkout session, treat the webhook as the source of truth, and short-circuit entirely for a valid voucher (C-17). There is no billing engine and none should be built (Non-Goal 2).

### Actors

Human roles are additive sets, not exclusive positions — the role check is "does this user's role set include X for this tenant", never "what is this user's role". Machine actors (crews, Stripe, SES) act only through their named capabilities; no crew ever writes an approval, and no reviewer action is automated.

### Events

Events drive the workflow seams: payment confirmation triggers provisioning, provisioning triggers seeding, answers trigger follow-up generation, submission and approval trigger notifications. Every notification is dual-channel (in-app plus SES email). All auth and review events also land in the tenant audit log — a WISP product must be able to demonstrate its own access accountability.

### Constraints

The nineteen named constraints C-01 through C-19 are normative; each cites the scenario that sources it. Constraint changes require changing the scenario first (spec-code alignment extends to Gherkin). The load-bearing ones are C-01 (tenant isolation), C-13 (watermark gate), C-14/C-15 (version discipline), and C-19 (AI degradation) — violating any of these is a stop-the-line event.

### Integrations

The LLM is behind a provider factory selected by environment configuration: Ollama with gemma-4-12B for development, Bedrock kimi-2.5 for production. No CrewAI crew may construct its own LLM client. Tavily is exposed to crews as a CrewAI tool only. Stripe integration is Checkout plus one webhook endpoint with idempotent handling. SES sends all transactional mail; in dev, a console email backend logs instead of sending.

### Non-Functional

Security posture must exceed what the product preaches: Argon2id, mandatory TOTP, 8-hour sessions, lockout, audit logging, EBS encryption at rest, and no tenant content in logs (C-18). Performance targets are modest by design — tens of firms, single-digit concurrent users per firm — which is exactly why per-tenant SQLite in WAL mode is the right call and why introducing Postgres or a queue would be over-engineering (Non-Goal 5).

### Risks

The three real risks: (1) LLM output quality for compiled answers — mitigated by the reviewer gate, which is a human control, not a hope; (2) subdomain provisioning correctness — mitigated by the wildcard cert and wildcard DNS so no per-tenant infrastructure action is needed at signup; (3) SQLite write contention during compilation bursts — mitigated by WAL mode and by the fact that compilation is per-domain and rare. A fourth, operational: the SSH allowlist pins one residential IP; Terraform exposes it as a variable so rotation is a one-line apply.

## 5. Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn; functional style, full type hints, pydantic v2 |
| Package manager | uv (backend), npm (frontend) |
| HTTP client | httpx (async, retries) |
| JSON | orjson |
| DB | SQLite (WAL), one file per tenant + control.db; raw SQL with parameterized queries via aiosqlite |
| Auth | argon2-cffi, pyotp (TOTP), itsdangerous (reset/invite tokens) |
| AI | CrewAI flows/crews; LLM factory: Ollama gemma-4-12B (dev), Bedrock kimi-2.5 (prod); Tavily tool |
| PDF | WeasyPrint from HTML template [ASSUMED] |
| Email | boto3 SES (prod), console backend (dev) |
| Payments | Stripe Checkout + webhook |
| Frontend | React 18 + Vite + TypeScript |
| Tests | pytest, pytest-bdd, pytest-asyncio, freezegun; vitest (frontend units); Playwright (full E2E) |
| Lint | ruff check + ruff format; eslint + prettier (frontend) |
| IaC | Terraform (AWS provider, personal profile), nginx, certbot DNS-01 wildcard |

## 6. Commands

```bash
# Backend
uv sync                                            # install
uv run uvicorn app.main:app --reload               # run dev API
uv run pytest tests/ -q                            # all backend tests
uv run pytest tests/steps -q                       # BDD suite
uv run pytest tests/steps/test_<feature>.py -q     # single feature
uv run pytest tests/steps/test_<feature>.py -q -k "<scenario substring>"   # single scenario
uv run pytest tests/unit -q                        # unit tests
uv run pytest --cov=app --cov-report=term-missing  # coverage
uv run ruff check . && uv run ruff format --check .  # lint

# Frontend (from frontend/)
npm install && npm run dev                         # run dev UI
npm run build                                      # production build
npm run test                                       # vitest units
npx playwright test                                # full E2E suite
npx playwright test e2e/<flow>.spec.ts             # single E2E flow

# Seed demo tenant (accounting firm, 10-50 employees, Drake Tax, South Carolina)
uv run python -m app.cli seed-demo

# Deploy (from infra/)
terraform init && terraform plan && terraform apply
```

## 7. Living Documentation

- **Pydantic v2 models** are the single source for entity shapes; FastAPI generates OpenAPI from them at `/openapi.json`.
- **Frontend types generated, never hand-written**: `npm run gen:api` runs openapi-typescript against the running dev API into `frontend/src/api/types.ts`. Regenerate whenever a pydantic model changes.
- **Feature files are living documentation**: `features/*.feature` are spec, not code. The agent never edits them without human approval; behavior changes update the scenario first.
- **Constraint registry**: C-01 through C-19 in Section 3 are referenced by ID in code comments at their enforcement points and in commit messages.

## 8. Task Decomposition

Each task lists the scenario IDs it must make pass (see TESTPLAN.md matrix). Scenario-exempt tasks say why.

**Task 01 — Repo scaffold and toolchain** (scenario-exempt: tooling)
Objective: monorepo skeleton (app/, frontend/, features/, tests/, infra/), uv + ruff + pytest + pytest-bdd wired, Vite React TS scaffold, Playwright installed, all Section 6 commands runnable green on empty suites.
Inputs: none. Output: running skeleton, CI-ready commands.
Acceptance: every Section 6 command exits 0.

**Task 02 — Tenancy core: control DB, tenant DB factory, subdomain resolution** (scenario-exempt: cross-cutting infrastructure; verified by unit tests + C-01 checks in every later integration test)
Objective: control.db schema (Tenant, Subscription, Voucher), per-tenant SQLite creation with schema migration-on-create, middleware resolving `<slug>.app.wisp.llc` (and `<slug>.localhost` in dev) to the tenant DB handle.
Acceptance: unit tests prove two tenants never share a connection; unknown slug yields a branded 404 page.

**Task 03 — Auth core: passwords, sessions, lockout** — Scenarios: AUTH-03, AUTH-05, AUTH-06
Objective: Argon2id hashing, 12-char policy, session issue/expiry (8h), failed-attempt counter and 15-minute lockout (C-02, C-03, C-05).
Acceptance: AUTH-03/05/06 green with freezegun-driven clocks; no real sleeps.

**Task 04 — TOTP enrollment and full login flow** — Scenarios: AUTH-01, AUTH-02, AUTH-04
Objective: pyotp secrets, mandatory enrollment interstitial at first login, TOTP verification counting toward lockout (C-04).
Acceptance: AUTH-01/02/04 green; login without TOTP impossible for any active user.

**Task 05 — Password reset** — Scenarios: AUTH-07
Objective: signed reset tokens (30-min expiry, C-06), email dispatch via backend abstraction.
Acceptance: AUTH-07 green; expired token path unit-tested.

**Task 06 — Signup, vitals, payment, provisioning** — Scenarios: SIGN-01, SIGN-02, SIGN-03, SIGN-04, SIGN-05
Objective: signup flow, vitals form validation, slug derivation + collision suggestion, Stripe Checkout session + idempotent webhook, voucher redemption (C-17), tenant provisioning event that creates the tenant DB, WISP version 1, and 14 domains in pending_questions.
Acceptance: all SIGN scenarios green with a stubbed Stripe client at integration level; declined card leaves no tenant DB file.

**Task 07 — Invitations, roles, deactivation** — Scenarios: USER-01, USER-02, USER-03, USER-04, USER-05, USER-06
Objective: invite tokens (7-day expiry, C-07), activation (password + TOTP), multi-role grants, duplicate-invite rejection, deactivation flagging domains (answers preserved).
Acceptance: all USER scenarios green.

**Task 08 — LLM factory, CrewAI base, Tavily tool** (scenario-exempt: enabling infrastructure; behavior verified through Tasks 09, 12, 13)
Objective: provider factory (env-driven Ollama vs Bedrock), CrewAI crew base with 1-retry exponential backoff and typed results, Tavily tool wrapper, fake-LLM and fake-Tavily test doubles.
Acceptance: unit tests cover provider selection, retry, and failure surfacing; no crew constructs its own client.

**Task 09 — Domain seeding crew and demo tenant** — Scenarios: SEED-01, SEED-02, SEED-03
Objective: SeederCrew producing 5-10 Yes-No questions per domain from industry + locale (C-08), async fan-out over 14 domains, per-domain retry on failure, "Questions pending" state, `seed-demo` CLI (SC accounting firm, Drake Tax).
Acceptance: SEED-01/02/03 green against the fake LLM; question count bounds enforced by validation, not prompt hope.

**Task 10 — Question management** — Scenarios: SEED-04, SEED-05, SEED-06
Objective: admin add/edit/disable/reinstate questions, per-domain regeneration guarded by zero-answers rule (C-16).
Acceptance: SEED-04/05/06 green.

**Task 11 — Notifications (in-app + SES)** (scenario-exempt as a standalone feature: every "should be notified" Then step across USER, ASSN, QSTN, REVW scenarios exercises it)
Objective: Notification entity, in-app feed endpoint, SES email backend with console fallback in dev, single notify() service used by all workflows.
Acceptance: unit tests for both channels; later scenario steps assert through the in-app feed.

**Task 12 — Domain assignment** — Scenarios: ASSN-01, ASSN-02, ASSN-03, ASSN-04, ASSN-05
Objective: one-contributor-one-reviewer assignment (C-10), replacement semantics with displaced-user notification, answer preservation, role-scoped visibility, admin gap flagging.
Acceptance: all ASSN scenarios green.

**Task 13 — Questionnaire flow** — Scenarios: QSTN-01, QSTN-04, QSTN-05, QSTN-06
Objective: answer capture, FollowUpCrew (cap 3, C-09, Tavily-assisted), skip-defers-but-blocks (C-11), save-and-resume position, outage waiver path (C-19) with contributor notice.
Acceptance: QSTN-01/04/05/06 green; followup cap enforced by validation.

**Task 14 — Compilation and submission** — Scenarios: QSTN-02, QSTN-03
Objective: CompilerCrew narrative generation from the full domain conversation, contributor preview, submission to in_review with contributor lock (C-12) and reviewer notification.
Acceptance: QSTN-02/03 green.

**Task 15 — Review workflow** — Scenarios: REVW-01, REVW-02, REVW-03, REVW-04, REVW-05
Objective: approve, edit + RevisionCrew + direct reviewer approval, defer, self-review warning, all-approved completing the version with admin notification.
Acceptance: all REVW scenarios green.

**Task 16 — Versioning and PDF export** — Scenarios: VERS-01, VERS-02, VERS-03, VERS-04, VERS-05
Objective: WeasyPrint HTML template with vitals + logo, DRAFT watermark gate (C-13), clone-forward new version, single-in-progress guard (C-14), immutable prior versions with export (C-15).
Acceptance: all VERS scenarios green; watermark asserted by inspecting generated PDF text layer.

**Task 17 — React frontend: auth, onboarding, dashboards** — Scenarios: E2E coverage of SIGN-01, AUTH-01, AUTH-02, USER-02
Objective: signup wizard (vitals per the field list), login + TOTP screens, role-aware dashboards with KPIs and progress, generated API types.
Acceptance: Playwright specs for signup-through-dashboard and login green against the dev stack with fake LLM.

**Task 18 — React frontend: questionnaire, review, export, versions** — Scenarios: E2E coverage of QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02
Objective: contributor question flow with follow-ups and skip, reviewer screens with self-review warning, export buttons, version history.
Acceptance: Playwright end-to-end pass of contribute → review → approve → export.

**Task 19 — Terraform, nginx, certbot, deployment** (scenario-exempt: infrastructure)
Objective: Terraform for EC2 (encrypted EBS), new SSH keypair, security group (443 world, 22 only 24.11.224.55/32 as a variable), elastic IP, personal AWS profile; nginx wildcard vhost + static frontend + uvicorn proxy; certbot DNS-01 wildcard for *.app.wisp.llc; systemd unit; deploy script.
Acceptance: terraform plan clean; documented bring-up produces a reachable demo tenant over TLS.

**Task 20 — Full Playwright regression suite** — Scenarios: remaining browser-level coverage per TESTPLAN Section 4
Objective: complete the "full Playwright coverage" decision — every feature has at least one browser-level spec.
Acceptance: `npx playwright test` green; TESTPLAN matrix E2E column has no gaps.

## 9. Quality Gates

Per task, three checkpoints:

- **Pre**: plan reviewed against the task's spec sections and scenario IDs before any code. Plan names which step definitions will be written first.
- **Mid**: the task's scenarios red for the right reason, then green; unit tests green; no other scenario broken (full BDD suite run).
- **Post**: cleanup pass (dead code, naming, formatting), `ruff check` and `ruff format --check` clean, TESTPLAN matrix status updated, constraint IDs cited in the commit message.

## 10. Open Questions and Assumptions

Collected [ASSUMED] defaults — override any of these and the spec plus affected scenarios update together:

- Password minimum 12 characters (C-05); reset links 30 minutes (C-06); invitations 7 days (C-07).
- Follow-up cap of 3 per question (C-09).
- WeasyPrint as PDF engine (OQ-2); t3.large instance (OQ-3); demo tenant recreated on deploy (OQ-4).
- Stripe webhook is the payment source of truth; the redirect page shows optimistic status (OQ-1).
- Slug derivation: lowercase, alphanumeric and hyphens, collisions suffixed with a numeral suggestion.
- No tenant content in logs (C-18); audit log covers auth and review events.
- Ollama runs on the developer workstation, not the EC2 instance; prod uses Bedrock only.

Open decision requiring the human: none blocking Task 01. OQ-1 through OQ-4 carry defaults rated low-to-medium impact.
