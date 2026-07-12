# Project Constitution: WISPGen

> This file contains immutable project rules. Every AI coding session must read this
> file before writing any code. These rules cannot be overridden by the agent without
> explicit human approval in the conversation.
>
> Last updated: 2026-07-09
> Stack: Python 3.12 / FastAPI / SQLite (per-tenant) / React + TypeScript / CrewAI

---

## 1. Coding Standards

### Language and Style
- Python 3.12, functional style preferred over class-based; classes only for pydantic models, CrewAI crews, and typed protocols.
- Full type hints everywhere. `Any` requires a comment justifying it.
- Formatting: `ruff format`. Linting: `ruff check` (zero warnings tolerated).
- Imports: stdlib → third-party → local, alphabetized within groups (ruff isort rules).
- `httpx` never `requests`; `orjson` never `json` for serialization; `aiosqlite` with parameterized SQL, never string-built queries.
- Frontend: TypeScript strict mode, eslint + prettier, functional components with hooks only.

### Naming Conventions
- Python files, functions, variables: snake_case. Constants: UPPER_SNAKE. Pydantic models and crews: PascalCase.
- TypeScript: camelCase functions and variables, PascalCase components, kebab-case file names.
- Constraint enforcement points carry a comment with the constraint ID, e.g. `# C-13: DRAFT watermark gate`.

### Preferred Pattern Example

```python
async def submit_domain(db: TenantDB, domain_id: int, contributor_id: int) -> DomainStatus:
    """Move a compiled domain to review; lock it for the contributor (C-12)."""
    domain = await get_domain(db, domain_id)
    if domain is None:
        raise NotFoundError(f"domain {domain_id}")
    if domain.status is not DomainStatus.IN_PROGRESS:
        raise ConflictError("domain is not submittable in its current state")
    compiled = await get_compiled_answer(db, domain_id)
    if compiled is None:
        raise ConflictError("compile the domain before submitting")
    await set_domain_status(db, domain_id, DomainStatus.IN_REVIEW)
    await notify(db, user_id=domain.reviewer_id, kind="domain_submitted", domain_id=domain_id)
    await audit(db, actor=contributor_id, event="domain.submitted", subject=f"domain:{domain_id}")
    return DomainStatus.IN_REVIEW
```

### Anti-Patterns — Do Not Write Code Like This

```python
# BAD: business rule buried in the router, HTTPException in domain logic,
# hand-rolled JSON, silent broad except
@app.post("/submit/{domain_id}")
async def submit(domain_id: int):
    try:
        row = await db.execute(f"SELECT * FROM domains WHERE id = {domain_id}")  # injection
        if row["status"] == "in_progress":
            ...
    except Exception:
        return json.dumps({"ok": False})  # swallowed error, wrong serializer
```

Routers translate; services decide. Domain code raises domain exceptions and never
imports FastAPI.

---

## 2. Testing Requirements

- BDD runner: **pytest-bdd**. Unit framework: **pytest** with pytest-asyncio. Clocks via **freezegun** — never `time.sleep` in tests (C-02, C-03 timing rules are clock-injected).
- Commands (must match SPEC.md Section 6 and TESTPLAN.md exactly):
  - All: `uv run pytest tests/ -q` · BDD: `uv run pytest tests/steps -q` · Units: `uv run pytest tests/unit -q`
  - Lint: `uv run ruff check . && uv run ruff format --check .`
  - Coverage: `uv run pytest --cov=app --cov-report=term-missing` — minimum 85% on `app/services` and `app/domain`.
  - Frontend: `npm run test` (vitest) · E2E: `npx playwright test`.
- Must be tested: every service function, every capability's error paths, all validation, all state transitions, tenant isolation (every integration test asserts it cannot read a second seeded tenant).
- Exempt from tests: generated OpenAPI types, configuration, migrations-on-create DDL strings.
- LLM and Tavily are ALWAYS test doubles in the suite. No test may call a real model or the network.
- Naming: `test_<module>.py`, `test_<behavior>_<outcome>`, e.g. `test_submit_domain_without_compiled_answer_raises_conflict`.

---

## 3. Error Handling

- Exception hierarchy:
  ```
  WispgenError
  ├── ValidationError
  ├── NotFoundError
  ├── AuthorizationError
  ├── ConflictError
  └── ExternalServiceError   (Stripe, SES, LLM, Tavily)
  ```
- API boundary: one exception handler maps the hierarchy to a consistent envelope `{"error": {"code", "message"}}`. Never leak stack traces, paths, or SQL. HTTP codes live only at this boundary.
- Service layer: raise domain exceptions; never `except Exception: pass`. Log with context before wrapping.
- External calls (LLM, Tavily, Stripe, SES): async via httpx or SDK, **one retry with exponential backoff**, then raise `ExternalServiceError`. Workflow code decides degradation (C-19: waive follow-ups, mark seeds pending) — the transport layer never decides silently.
- Logging: structured, no tenant answer content or vitals ever (C-18). Log constraint IDs when a guard fires.

---

## 4. Dependency Rules

- Allowed without asking: stdlib and the approved list below.
- Ask first: any other package, frontend or backend.
- Never: ORMs (raw parameterized SQL only), Celery or any queue broker (Non-Goal 5), `requests`, CSS-in-JS libraries, packages unmaintained for 12+ months.
- Approved: fastapi, uvicorn, pydantic v2, aiosqlite, httpx, orjson, argon2-cffi, pyotp, itsdangerous, crewai, boto3, stripe, weasyprint, tavily-python, pytest, pytest-bdd, pytest-asyncio, pytest-cov, freezegun, ruff · react, react-router, vite, typescript, vitest, playwright, eslint, prettier, openapi-typescript.

---

## 5. Spec-Code Alignment

- SPEC.md is the single source of truth for behavior; `features/*.feature` are spec with equal standing.
- If implementation must deviate: update SPEC.md and the affected scenario FIRST, get human approval, then code. Never commit code contradicting either.
- Every commit message references its task number and the constraint IDs it touches (e.g. `task-14: compilation + submission (C-12)`).
- Spec ambiguity discovered mid-task → raise as an open question; do not silently resolve in code.

---

## 6. Plan-Before-Act Protocol

- Every task starts in plan mode: approach, files to touch, which scenario step definitions are written first, which constraints apply. Human approves before executable code.
- Exempt from planning: typo fixes, comment corrections, formatting-only changes, lockfile refreshes from an approved dependency change.
- A previously green scenario turning red is a **stop-the-line event**: halt, report, await direction. Never "fix" it by editing the scenario.

---

## 7. Agent Boundaries

**ALWAYS**
- Read this file and the current task's spec sections before coding.
- Run the full BDD suite, unit suite, and lint before declaring a task done; update the TESTPLAN matrix status.
- Use the LLM provider factory and the notify() service; cite constraint IDs at enforcement points.
- Keep every change inside the current task's file scope.

**ASK FIRST**
- Adding any dependency; changing any DB schema after Task 02; deleting any file; touching infra/ outside Task 19; changing nginx, systemd, or Terraform variables; modifying CI configuration; altering the exception hierarchy or error envelope.

**NEVER**
- Edit `features/*.feature` without explicit human approval in the conversation — feature files are spec, not code.
- Edit `constitution.md` or weaken a named constraint (C-01 … C-19).
- Skip, delete, or `xfail` a test to get green; disable lint rules inline without approval.
- Call a real LLM, Tavily, Stripe, or SES endpoint from tests.
- Write code that opens another tenant's database file or accepts a tenant ID from request input instead of the resolved subdomain (C-01).
- Log tenant answers, vitals, secrets, or TOTP seeds (C-18).
- Force-push, rewrite published history, or commit `.env` files.

---

## 8. Quality Gates

- **Pre**: plan approved; plan names target scenario IDs and first step definitions.
- **Mid**: task scenarios red-for-the-right-reason then green; unit tests green; full BDD suite green (nothing else broke).
- **Post**: cleanup pass (dead code, naming, formatting), lint clean, coverage threshold held, TESTPLAN matrix updated, commit message cites task + constraints.

"Done" claims with silently skipped steps are treated as failures. Surface uncertainty; never bury it.

---

## 9. Git Workflow

- Branches: `task-NN-short-desc` (e.g. `task-06-signup-payment`).
- Commits: conventional prefix + task ref, e.g. `feat(task-06): voucher redemption path (C-17)`.
- One task per PR; PR description lists scenario IDs made green and links spec sections. Squash-merge. CI (tests + lint) must pass — no exceptions.

---

## 10. Context Management

- Task files and plans stay under 200 lines; a task references at most three SPEC.md sections.
- New session per task: load constitution.md, the task block, its scenario files, and TESTPLAN rows — not the whole spec.
- Long-running work across sessions leaves a `HANDOFF.md` note: state, next step, open questions. Delete it when the task closes.
- Never paste tenant data, real API keys, or the full SPEC.md into a sub-agent prompt; pass section references.
