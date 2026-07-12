# TESTPLAN: WISPGen

## 1. Test Strategy

The BDD runner is **pytest-bdd**: it binds Gherkin scenarios to plain pytest tests, shares fixtures with the unit suite, runs under the same `uv run pytest` toolchain, and keeps one report for both loops. The unit framework is pytest with pytest-asyncio; timing behaviors (8-hour sessions, 15-minute lockouts, 30-minute reset links, 7-day invitations) are tested with freezegun clock injection — never real waits.

The outer loop is the scenario: for each task, its scenarios' step definitions are written first and must fail because implementation is missing (not because glue is missing). The inner loop is unit TDD beneath those steps. Browser truth comes from Playwright: per the "full coverage" decision, every feature carries at least one browser-level spec, with API-level pytest-bdd carrying the exhaustive variant matrix so the Playwright suite stays fast enough to run on every task.

Definition of done for a task: its mapped scenarios green, its acceptance criteria checkable, unit tests green, lint clean, coverage threshold held, and the FULL BDD suite green — a task that breaks another scenario is not done.

## 2. Frameworks and Commands

| Purpose | Tool | Command |
|---|---|---|
| BDD suite (all) | pytest-bdd | `uv run pytest tests/steps -q` |
| Single feature | pytest-bdd | `uv run pytest tests/steps/test_<feature>.py -q` |
| Single scenario | pytest-bdd | `uv run pytest tests/steps/test_<feature>.py -q -k "<scenario substring>"` |
| Unit tests | pytest | `uv run pytest tests/unit -q` |
| Lint | ruff | `uv run ruff check . && uv run ruff format --check .` |
| Coverage | pytest-cov | `uv run pytest --cov=app --cov-report=term-missing` |
| Frontend units | vitest | `npm run test` |
| E2E (all) | Playwright | `npx playwright test` |
| E2E (single flow) | Playwright | `npx playwright test e2e/<flow>.spec.ts` |

Commands match SPEC.md Section 6 exactly. If they diverge, fix both.

## 3. Step Definition Plan

```
tests/
├── steps/
│   ├── conftest.py                      # app + tenant fixtures, fake LLM, fake Tavily,
│   │                                    # fake Stripe, console email, frozen clock factory
│   ├── common_steps.py                  # shared Givens: provisioned tenant, enrolled user,
│   │                                    # seeded domain, assigned domain, signed-in role
│   ├── test_signup_and_onboarding.py
│   ├── test_authentication.py
│   ├── test_user_and_role_management.py
│   ├── test_domain_seeding_and_questions.py
│   ├── test_domain_assignment.py
│   ├── test_contributor_questionnaire.py
│   ├── test_review_workflow.py
│   └── test_wisp_versioning_and_export.py
└── unit/
    └── test_<module>.py                 # one per app module
frontend/e2e/
    ├── signup.spec.ts, auth.spec.ts, users.spec.ts, seeding.spec.ts,
    ├── assignment.spec.ts, questionnaire.spec.ts, review.spec.ts, export.spec.ts
```

Rules: one steps module per feature file; cross-feature Givens live in `common_steps.py`; test data built by factory functions in `conftest.py` (`make_tenant()`, `make_user(roles=...)`, `make_seeded_domain()`) — never inline literals repeated across steps; every integration fixture seeds a second tenant and asserts it is untouched (C-01).

## 4. Traceability Matrix

| Scenario ID | Scenario | Feature file | Level | Steps module | SPEC Task | Status |
|---|---|---|---|---|---|---|
| SIGN-01 | Card signup provisions workspace | signup-and-onboarding | integration | test_signup_and_onboarding | Task 06 | planned |
| SIGN-02 | Voucher skips card payment | signup-and-onboarding | integration | test_signup_and_onboarding | Task 06 | planned |
| SIGN-03 | Declined card leaves no workspace | signup-and-onboarding | integration | test_signup_and_onboarding | Task 06 | planned |
| SIGN-04 | Workspace address must be unique | signup-and-onboarding | integration | test_signup_and_onboarding | Task 06 | planned |
| SIGN-05 | Corporate vitals validation (outline) | signup-and-onboarding | integration | test_signup_and_onboarding | Task 06 | planned |
| AUTH-01 | First login requires TOTP enrollment | authentication | integration | test_authentication | Task 04 | planned |
| AUTH-02 | Login with password and TOTP | authentication | integration | test_authentication | Task 04 | planned |
| AUTH-03 | Wrong password rejected | authentication | integration | test_authentication | Task 03 | planned |
| AUTH-04 | Wrong TOTP counts toward lockout | authentication | integration | test_authentication | Task 04 | planned |
| AUTH-05 | Lock after 5 failed attempts | authentication | integration | test_authentication | Task 03 | planned |
| AUTH-06 | Expired session preserves saved work | authentication | integration | test_authentication | Task 03 | planned |
| AUTH-07 | Password reset via 30-min link | authentication | integration | test_authentication | Task 05 | planned |
| USER-01 | Invite user with two roles | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| USER-02 | Invited user activates account | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| USER-03 | One user holds all three roles | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| USER-04 | Duplicate invitation rejected | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| USER-05 | Expired invitation link refused | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| USER-06 | Deactivation flags domains, keeps answers | user-and-role-management | integration | test_user_and_role_management | Task 07 | planned |
| SEED-01 | 14 domains seeded, 5-10 questions each | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 09 | planned |
| SEED-02 | Demo company after deployment | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 09 | planned |
| SEED-03 | Research outage degrades gracefully | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 09 | planned |
| SEED-04 | Admin adds custom question | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 10 | planned |
| SEED-05 | Admin disables seeded question | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 10 | planned |
| SEED-06 | Regeneration only when unanswered | domain-seeding-and-questions | integration | test_domain_seeding_and_questions | Task 10 | planned |
| ASSN-01 | Assign contributor and reviewer | domain-assignment | integration | test_domain_assignment | Task 12 | planned |
| ASSN-02 | One contributor, one reviewer at a time | domain-assignment | integration | test_domain_assignment | Task 12 | planned |
| ASSN-03 | Reassignment preserves work | domain-assignment | integration | test_domain_assignment | Task 12 | planned |
| ASSN-04 | Contributors see only assigned domains | domain-assignment | integration | test_domain_assignment | Task 12 | planned |
| ASSN-05 | Unassigned domains flagged to Admin | domain-assignment | integration | test_domain_assignment | Task 12 | planned |
| QSTN-01 | Answer triggers up to 3 AI follow-ups | contributor-questionnaire | integration | test_contributor_questionnaire | Task 13 | planned |
| QSTN-02 | AI compiles domain final answer | contributor-questionnaire | integration | test_contributor_questionnaire | Task 14 | planned |
| QSTN-03 | Submission sends domain to review | contributor-questionnaire | integration | test_contributor_questionnaire | Task 14 | planned |
| QSTN-04 | Skips defer but block submission | contributor-questionnaire | integration | test_contributor_questionnaire | Task 13 | planned |
| QSTN-05 | Save and resume exact progress | contributor-questionnaire | integration | test_contributor_questionnaire | Task 13 | planned |
| QSTN-06 | AI outage falls back to plain answer | contributor-questionnaire | integration | test_contributor_questionnaire | Task 13 | planned |
| REVW-01 | Reviewer approves compiled answer | review-workflow | integration | test_review_workflow | Task 15 | planned |
| REVW-02 | Edit produces AI revision, direct approval | review-workflow | integration | test_review_workflow | Task 15 | planned |
| REVW-03 | Reviewer defers decision | review-workflow | integration | test_review_workflow | Task 15 | planned |
| REVW-04 | Self-review allowed with warning | review-workflow | integration | test_review_workflow | Task 15 | planned |
| REVW-05 | All approved completes the WISP | review-workflow | integration | test_review_workflow | Task 15 | planned |
| VERS-01 | Draft export carries watermark | wisp-versioning-and-export | integration | test_wisp_versioning_and_export | Task 16 | planned |
| VERS-02 | Complete WISP exports clean | wisp-versioning-and-export | integration | test_wisp_versioning_and_export | Task 16 | planned |
| VERS-03 | New version clones approved baseline | wisp-versioning-and-export | integration | test_wisp_versioning_and_export | Task 16 | planned |
| VERS-04 | Only one version in progress | wisp-versioning-and-export | integration | test_wisp_versioning_and_export | Task 16 | planned |
| VERS-05 | Prior versions remain exportable | wisp-versioning-and-export | integration | test_wisp_versioning_and_export | Task 16 | planned |

Browser-level duplicates (full Playwright coverage, Tasks 17, 18, 20): every scenario above gains an `e2e` row realized as a Playwright spec; the canonical mapping is one spec file per feature (Section 3). Playwright specs assert user-visible outcomes only; exhaustive variants stay at the pytest-bdd level.

Rules: every scenario has exactly one owning SPEC task; Tasks 01, 02, 08, 11, 19 are scenario-exempt with justifications in SPEC.md Section 8. Status values: planned, red, green, refactored. Reference scenario IDs in commit messages.

## 5. Acceptance Criteria Coverage

| Criterion (docs/bdd/acceptance-criteria.md) | Covered by | Gap? |
|---|---|---|
| Signup and Onboarding (8 criteria) | SIGN-01..05; slug rules + logo upload: unit tests Task 06; extensible tier model: unit test Task 06 | no |
| Authentication (10 criteria) | AUTH-01..07; Argon2id + 12-char policy: unit tests Task 03; audit log: unit tests Task 03/04 | no |
| User and Role Management (6 criteria) | USER-01..06 | no |
| Domain Seeding and Questions (6 criteria) | SEED-01..06 | no |
| Domain Assignment (4 criteria) | ASSN-01..05 | no |
| Contributor Questionnaire (8 criteria) | QSTN-01..06; Tavily-assisted follow-ups: unit test Task 13 (tool invoked on fake); WIP percentage: ASSN-04 + unit test | no |
| Review Workflow (6 criteria) | REVW-01..05 | no |
| Versioning and Export (6 criteria) | VERS-01..05; version history listing: VERS-05 | no |
| Cross-cutting: tenant isolation (C-01) | isolation assertion in every integration fixture + Task 02 unit tests | no |
| Cross-cutting: wildcard subdomain resolution | Task 02 unit tests; e2e smoke on demo tenant | no |
| Cross-cutting: EBS encryption at rest | NOT automated — verified by `terraform plan` review in Task 19 | YES (manual) |
| Cross-cutting: LLM provider switching | Task 08 unit tests (factory selection by env) | no |
| Cross-cutting: no tenant data in logs (C-18) | log-capture unit tests on notify/audit/error paths, Task 03 + 13 | no |

The single YES is deliberate: infrastructure encryption is a Terraform property, verified at plan review, not by the app test suite. Carried in the Architect Review Summary.

## 6. TDD Loop per Task

1. Write step definitions for the task's scenarios; run — red for the right reason (missing implementation, not missing glue).
2. Write unit tests beneath the steps; red.
3. Implement minimum code: units green, then scenarios green.
4. Refactor green; run lint.
5. Run the FULL BDD suite; a broken neighbor means the task is not done.
6. Check the task's acceptance criteria boxes; update matrix status; cite scenario and constraint IDs in the commit.

## 7. Test Data and Fixtures

- Factories: `make_tenant(slug=...)`, `make_user(email, roles, enrolled=True)`, `make_seeded_domain(code, questions=8)`, `make_answered_domain(...)`, `make_compiled_domain(...)`.
- Named users across suites: `admin@palmettotax.com`, `jane@palmettotax.com` (Contributor), `sam@palmettotax.com` (Reviewer or multi-role per scenario).
- Doubles (from conftest): FakeLLM (deterministic, per-crew canned outputs, failure mode switch), FakeTavily, FakeStripe (succeed, decline, webhook replay), console email backend capturing messages for "notified" assertions, frozen clock factory.
- Each scenario owns its state through Given steps; tenant DBs are created in tmp_path per test and discarded — no shared mutable state, no scenario ordering.
- Env for test runs: `WISPGEN_ENV=test`, `LLM_PROVIDER=fake`, `EMAIL_BACKEND=console`, `STRIPE_CLIENT=fake`.

## 8. Non-Functional Verification

- Timing (8h session, 15-min lockout, 30-min reset, 7-day invite): freezegun clock advance — never sleeps.
- Retry policy: FakeLLM programmed to fail-once-then-succeed proves single retry; fail-twice proves waiver path (C-19).
- Tenant isolation (C-01): every integration fixture seeds tenant B and asserts zero reads or writes against it after exercising tenant A.
- Log hygiene (C-18): caplog assertions that answer text, vitals values, and TOTP secrets never appear on any tested path.
- Watermark gate (C-13): extract PDF text layer and assert DRAFT present or absent by approval state.
- Manual: EBS encryption, security group rules, wildcard cert issuance — reviewed at `terraform plan` (Task 19) against a written checklist in `infra/README.md`.
