# WISPGen

Multi-tenant SaaS that generates Written Information Security Programs for small accounting firms.

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

## Project documents

- `constitution.md` — immutable project rules
- `SPEC.md` — behavior spec and task decomposition
- `TESTPLAN.md` — traceability matrix and TDD loop
- `AGENTS.md` — OpenCode session guidance
- `AGENT.md` — bootstrap prompt
- `docs/superpowers/plans/2026-07-12-wispgen-master-plan.md` — implementation master plan
