# Acceptance Criteria Coverage — DRAFT

> **DRAFT — pending human approval.** This document maps acceptance criteria to their automated coverage. It will be updated as tasks complete.

| Capability area | Criteria | Covered by | Gap? |
|---|---|---|---|
| Signup and Onboarding (8 criteria) | Slug rules, logo upload, extensible tier model, card signup, voucher signup, declined card, unique address, vitals validation | SIGN-01..05; slug + vitals unit tests Task 06 | no |
| Authentication (10 criteria) | Argon2id, 12-char policy, audit log, TOTP enrollment, password + TOTP login, wrong password, wrong TOTP lockout, 5-failure lock, expired session preserves work, 30-min reset | AUTH-01..07; auth + audit unit tests Tasks 03, 04, 05 | no |
| User and Role Management (6 criteria) | Multi-role invite, activation, all three roles, duplicate invite rejection, expired invite, deactivation preserves answers | USER-01..06 | no |
| Domain Seeding and Questions (6 criteria) | 14 domains, 5-10 questions, demo company, outage grace, custom questions, disable/reinstate, regeneration guard | SEED-01..06 | no |
| Domain Assignment (4 criteria) | One contributor + one reviewer, reassignment preserves work, role-scoped visibility, admin gap flag | ASSN-01..05 | no |
| Contributor Questionnaire (8 criteria) | Answer triggers follow-ups, cap 3, skip defers/blocks, save/resume, AI outage waiver, Tavily-assisted follow-ups | QSTN-01..06; Tavily tool unit test Task 13 | no |
| Review Workflow (6 criteria) | Approve, edit + AI revision + direct approval, defer, self-review warning, all-approved completes WISP | REVW-01..05 | no |
| Versioning and Export (6 criteria) | Draft watermark, clean complete export, clone-forward, single in-progress, immutable prior versions, version history | VERS-01..05 | no |
| Cross-cutting: tenant isolation (C-01) | One SQLite file per tenant; no cross-tenant access | Isolation assertion in every integration fixture + Task 02 unit tests | no |
| Cross-cutting: wildcard subdomain resolution | `*.app.wisp.llc` and `*.localhost` dev resolution | Task 02 unit tests; e2e smoke on demo tenant | no |
| Cross-cutting: EBS encryption at rest | Terraform property | Verified by `terraform plan` review in Task 19 | YES — manual |
| Cross-cutting: LLM provider switching | Ollama dev, Bedrock prod | Task 08 unit tests | no |
| Cross-cutting: no tenant data in logs (C-18) | No answers, vitals, or TOTP secrets in logs | Log-capture unit tests Tasks 03, 13 | no |

The single YES is deliberate: infrastructure encryption is a Terraform property verified at plan review, not by the app test suite.
