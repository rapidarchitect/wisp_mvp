# AGENTS.md — WISPGen

Compact guidance for OpenCode sessions working on WISPGen.

## What this repo is

WISPGen is a multi-tenant SaaS that generates Written Information Security Programs for small accounting firms. This repository is currently a **spec/scaffold project**: it contains the planning documents but no application code yet. The first implementation task is Task 01 (repo scaffold and toolchain).

## Read before writing code

Read these files in this order on every new session:

1. `constitution.md` — immutable project rules (NEVER edit without explicit approval).
2. `SPEC.md` — behavior spec, tech stack, commands, and task decomposition.
3. `TESTPLAN.md` — traceability matrix, step definition layout, TDD loop.
4. `AGENT.md` — bootstrap prompt for new Claude Code sessions.

## Current repo state

- No source code yet; `app/`, `frontend/`, `tests/`, `infra/` directories do not exist.
- `features/` and `docs/bdd/` are referenced in the specs but not yet created.
- All 20 SPEC tasks are in `planned` status.

## Workflow

- **Plan before code**: every task starts in plan mode; get approval before executable code. Exempt: typo fixes, comments, formatting-only changes, lockfile refreshes.
- **TDD order** for each task:
  1. Write failing pytest-bdd step definitions for the task's scenario IDs (red for missing implementation, not missing glue).
  2. Write failing unit tests beneath them.
  3. Implement minimum code — units first, then scenarios.
  4. Refactor with everything green.
  5. Run the **full BDD suite** (`uv run pytest tests/steps -q`); a broken neighbor means the task is not done.
  6. Run lint and update `TESTPLAN.md` matrix status.
- A previously green scenario turning red is a **stop-the-line event**: halt and report.

## Developer commands

```bash
# Backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest tests/ -q
uv run pytest tests/steps -q
uv run pytest tests/steps/test_<feature>.py -q
uv run pytest tests/steps/test_<feature>.py -q -k "<scenario substring>"
uv run pytest tests/unit -q
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check . && uv run ruff format --check .
uv run python -m app.cli seed-demo

# Frontend (from frontend/)
npm install && npm run dev
npm run build
npm run test
npx playwright test
npx playwright test e2e/<flow>.spec.ts
```

## Hard rules

- Do not create or edit `features/*.feature` without explicit human approval — feature files are spec.
- Do not edit `constitution.md` or weaken constraints C-01 through C-19.
- Do not add dependencies beyond the constitution's approved list without asking.
- Never call real LLM, Tavily, Stripe, or SES endpoints from tests.
- Never open another tenant's database file; tenant identity comes from the resolved subdomain only (C-01).
- Never log tenant answers, vitals, or TOTP secrets (C-18).
- Do not skip, delete, or `xfail` tests to get green.

## Git

- Branch: `task-NN-short-desc`.
- Commit: `feat(task-06): voucher redemption path (C-17)` — cite task and constraint IDs.
- One task per PR; squash-merge; CI must pass.

## Frontend type generation

Frontend types are generated from the running dev API. Regenerate whenever Pydantic models change:

```bash
npm run gen:api   # openapi-typescript -> frontend/src/api/types.ts
```

## Deploy

Task 19 owns Terraform, nginx, certbot, and deployment. Do not touch `infra/` outside Task 19 without asking.
