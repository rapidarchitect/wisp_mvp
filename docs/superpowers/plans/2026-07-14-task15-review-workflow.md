# Task 15 — Review Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reviewer-side actions that approve, revise, or defer a submitted domain, including self-review warnings and WISP version completion.

**Architecture:** A `review.py` service orchestrates the three review actions, delegates narrative revision to a `RevisionCrew`, and triggers version completion when all 14 domains are approved. A thin router exposes the actions under `POST /domains/{code}/(approve|revise|defer)`.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, uv, pytest-bdd, ruff.

## Global Constraints

- Python 3.12, FastAPI, pydantic v2.
- `uv` only; no pip.
- Use `httpx` for HTTP, `orjson` for JSON, `aiosqlite` for tenant DB.
- One SQLite file per tenant (C-01).
- Domain is read-only for contributor while `in_review` (C-12).
- AI outage after one retry degrades gracefully (C-19).
- Never log tenant answers or vitals (C-18).
- Feature files require explicit human approval (AGENTS.md).
- Tests: red for missing implementation, not missing glue; full BDD suite green before done.

---

## File Map

| File | Responsibility |
|---|---|
| `app/crews/revision_crew.py` | New. Builds prompt, calls LLM, returns revised narrative. |
| `app/services/review.py` | New. `approve_domain`, `revise_and_approve`, `defer_domain`. |
| `app/api/routers/review.py` | New. `POST /domains/{code}/approve`, `/revise`, `/defer`. |
| `app/main.py` | Modify. Register `review_router`. |
| `app/services/notification_templates.py` | Modify. Add `domain_approved`, `domain_revised_and_approved`, `domain_deferred`, `wisp_complete`. |
| `features/review-workflow.feature` | Create (human approval required). REVW-01..05 scenarios. |
| `tests/unit/test_revision_crew.py` | New. Unit tests for `RevisionCrew`. |
| `tests/unit/test_services_review.py` | New. Unit tests for review service. |
| `tests/unit/test_routers_review.py` | New. Router-level tests. |
| `tests/steps/test_review_workflow.py` | Modify/Create. BDD step definitions for REVW-01..05. |
| `tests/steps/conftest.py` | Modify. Mount `review_router`. |
| `frontend/e2e/review-workflow.spec.ts` | New. Playwright API smoke test. |
| `TESTPLAN.md` | Modify. Update matrix statuses. |

---

### Task 1: Create `RevisionCrew`

**Files:**
- Create: `app/crews/revision_crew.py`
- Test: `tests/unit/test_revision_crew.py`

**Interfaces:**
- Consumes: `create_llm` from `app.ai.llm_factory`, `CrewBase` from `app.ai.crew_base`.
- Produces: `RevisionCrew(db, domain_code, domain_name, current_narrative, conversation, llm=None).revise(prompt) -> str`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.ai.fakes import FakeLLM
from app.crews.revision_crew import RevisionCrew


@pytest.mark.asyncio
async def test_revision_crew_returns_revised_narrative():
    crew = RevisionCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        current_narrative="We lock the doors.",
        conversation=[],
        llm=FakeLLM(default="We lock the doors and badge visitors."),
    )
    result = await crew.revise("Add detail about visitor badges")
    assert isinstance(result, str)
    assert "badge" in result.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_revision_crew.py -v`
Expected: `ModuleNotFoundError: No module named 'app.crews.revision_crew'`

- [ ] **Step 3: Write minimal implementation**

Create `app/crews/revision_crew.py`:

```python
"""CrewAI crew that revises a compiled domain narrative per reviewer prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


class RevisionCrew(CrewBase):
    """Revise a compiled narrative according to a reviewer prompt."""

    def __init__(
        self,
        db: "TenantDB" | None,
        *,
        domain_code: str,
        domain_name: str,
        current_narrative: str,
        conversation: list[dict[str, Any]],
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.current_narrative = current_narrative
        self.conversation = conversation
        self.llm = llm or create_llm()

    async def revise(self, revision_prompt: str) -> str:
        """Return a revised narrative paragraph."""
        return await self.run_with_retry(
            lambda: self._revise_once(revision_prompt), max_retries=1
        )

    async def _revise_once(self, revision_prompt: str) -> str:
        prompt = self._build_prompt(revision_prompt)
        raw = await self._call_llm(prompt)
        return raw.strip()

    def _build_prompt(self, revision_prompt: str) -> str:
        lines = [f"Domain: {self.domain_name} ({self.domain_code})"]
        lines.append("Current narrative:")
        lines.append(self.current_narrative)
        lines.append("Reviewer instruction:")
        lines.append(revision_prompt)
        lines.append(
            "Rewrite the current narrative as a single professional paragraph "
            "for a Written Information Security Program, incorporating the reviewer instruction. "
            "Return only the paragraph, with no headings or lists."
        )
        return "\n\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        result = self.llm.call(prompt)
        if isinstance(result, str):
            return result
        raise RuntimeError("LLM did not return a string response")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_revision_crew.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/crews/revision_crew.py tests/unit/test_revision_crew.py
uv run ruff check app/crews/revision_crew.py tests/unit/test_revision_crew.py
uv run ruff format app/crews/revision_crew.py tests/unit/test_revision_crew.py
git commit -m "feat(task-15): RevisionCrew for reviewer-driven narrative edits (C-19)"
```

---

### Task 2: Create review service

**Files:**
- Create: `app/services/review.py`
- Test: `tests/unit/test_services_review.py`

**Interfaces:**
- Consumes: `TenantDB`, `RevisionCrew`, `audit`, `notify`, `notification_templates`; helper from `app.services.compilation` to load answered questions.
- Produces: `approve_domain(db, *, reviewer_id, code) -> dict`, `revise_and_approve(db, *, reviewer_id, code, revision_prompt, llm=None) -> dict`, `defer_domain(db, *, reviewer_id, code) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_services_review.py`:

```python
import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import AuthorizationError, ConflictError
from app.services.review import approve_domain, defer_domain, revise_and_approve


@pytest.fixture
async def db(tmp_path):
    return await init_tenant_db(str(tmp_path), "palmetto")


@pytest.mark.asyncio
async def test_approve_domain_requires_in_review(db):
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) VALUES (?, ?, ?, ?, ?, ?)",
        ("r@test.com", "x", '["reviewer"]', "active", "s", 1),
    )
    reviewer_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("r@test.com",)))["id"]
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    version_id = (await db.fetchone("SELECT id FROM wisp_versions"))["id"]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "assigned"),
    )
    domain_id = (await db.fetchone("SELECT id FROM domains"))["id"]
    await db.execute(
        "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)",
        (domain_id, reviewer_id, reviewer_id),
    )
    await db.commit()
    with pytest.raises(ConflictError):
        await approve_domain(db, reviewer_id=reviewer_id, code="AC")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_services_review.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.review'`

- [ ] **Step 3: Write minimal implementation**

Create `app/services/review.py`:

```python
"""Review workflow service (Task 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.crews.revision_crew import RevisionCrew
from app.db.tenant import TenantDB
from app.exceptions import (
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
)
from app.services import compilation as compilation_service
from app.services.audit import audit
from app.services.notifications import notify


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def approve_domain(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
) -> dict:
    """Approve a domain that is currently in review."""
    domain, compiled = await _resolve_domain_with_compiled(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError("domain not assigned to this reviewer", code="forbidden")
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    await db.execute(
        "UPDATE compiled_answers SET approved_at = ? WHERE id = ?",
        (_now(), compiled["id"]),
    )
    await db.execute(
        "UPDATE domains SET status = 'approved' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_approved",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["contributor_id"],
        kind="domain_approved",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )

    wisp_complete = await _maybe_complete_version(db, version_id=domain["wisp_version_id"])
    if wisp_complete:
        admin = await _find_admin(db)
        if admin is not None:
            await notify(
                db,
                user_id=admin["id"],
                kind="wisp_complete",
                payload={},
                channel="in_app",
            )
        await audit(
            db,
            actor_user_id=reviewer_id,
            event_type="wisp_completed",
            subject=f"version:{domain['wisp_version_id']}",
            detail="",
            commit=False,
        )

    await db.commit()

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "approved",
        "self_review": domain["contributor_id"] == reviewer_id,
        "wisp_complete": wisp_complete,
    }


async def revise_and_approve(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
    revision_prompt: str,
    llm: Any | None = None,
) -> dict:
    """Revise the compiled narrative and immediately approve the domain."""
    domain, compiled = await _resolve_domain_with_compiled(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError("domain not assigned to this reviewer", code="forbidden")
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    questions = await compilation_service._load_answered_questions(
        db, domain_id=domain["id"], contributor_id=domain["contributor_id"]
    )
    conversation = [
        {
            "question": q["text"],
            "answer": "skipped" if q["answer"]["skipped"] else q["answer"]["value"],
            "followups": [
                {"text": f["text"], "response": f.get("response_text") or ""}
                for f in q["answer"].get("followups", [])
            ],
        }
        for q in questions
    ]

    crew = RevisionCrew(
        db,
        domain_code=code,
        domain_name=domain["name"],
        current_narrative=compiled["narrative_text"],
        conversation=conversation,
        llm=llm,
    )
    try:
        new_narrative = await crew.revise(revision_prompt)
    except Exception as exc:
        raise ExternalServiceError(
            "revision failed; please retry",
            code="llm_unavailable",
        ) from exc

    await db.execute(
        """
        UPDATE compiled_answers
        SET narrative_text = ?, revised_by_reviewer_id = ?
        WHERE id = ?
        """,
        (new_narrative, reviewer_id, compiled["id"]),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_revised",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )

    # Reuse approve logic after persisting the revision.
    return await approve_domain(db, reviewer_id=reviewer_id, code=code)


async def defer_domain(
    db: TenantDB,
    *,
    reviewer_id: int,
    code: str,
) -> dict:
    """Return a domain to the contributor for more information."""
    domain = await _resolve_domain(db, code)
    if domain["reviewer_id"] != reviewer_id:
        raise AuthorizationError("domain not assigned to this reviewer", code="forbidden")
    if domain["status"] != "in_review":
        raise ConflictError("domain is not in review", code="domain_not_in_review")

    await db.execute(
        "UPDATE domains SET status = 'in_progress' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=reviewer_id,
        event_type="domain_deferred",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["contributor_id"],
        kind="domain_deferred",
        payload={"domain_name": domain["name"]},
        channel="in_app",
    )
    await db.commit()

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "in_progress",
    }


async def _resolve_domain(db: TenantDB, code: str) -> dict[str, Any]:
    version = await db.fetchone(
        "SELECT id FROM wisp_versions WHERE status = 'in_progress' ORDER BY number DESC LIMIT 1"
    )
    if version is None:
        raise NotFoundError("no in-progress version")

    domain = await db.fetchone(
        """
        SELECT d.*, a.contributor_id, a.reviewer_id
        FROM domains d
        LEFT JOIN domain_assignments a ON a.domain_id = d.id
        WHERE d.wisp_version_id = ? AND d.code = ?
        """,
        (version["id"], code),
    )
    if domain is None:
        raise NotFoundError("domain not found")
    return dict(domain)


async def _resolve_domain_with_compiled(db: TenantDB, code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    domain = await _resolve_domain(db, code)
    compiled = await db.fetchone(
        "SELECT * FROM compiled_answers WHERE domain_id = ?",
        (domain["id"],),
    )
    if compiled is None:
        raise ConflictError("domain has no compiled answer", code="missing_compiled_answer")
    return domain, dict(compiled)


async def _maybe_complete_version(db: TenantDB, *, version_id: int) -> bool:
    total = await db.fetchone(
        "SELECT COUNT(*) AS count FROM domains WHERE wisp_version_id = ?",
        (version_id,),
    )
    approved = await db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM domains
        WHERE wisp_version_id = ? AND status = 'approved'
        """,
        (version_id,),
    )
    if approved["count"] == total["count"]:
        await db.execute(
            "UPDATE wisp_versions SET status = 'complete', completed_at = ? WHERE id = ?",
            (_now(), version_id),
        )
        return True
    return False


async def _find_admin(db: TenantDB) -> dict[str, Any] | None:
    import orjson

    rows = await db.fetchall("SELECT id, roles FROM users WHERE status = 'active'")
    for row in rows:
        roles = orjson.loads(row["roles"])
        if "admin" in roles:
            return dict(row)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_services_review.py -v`
Expected: PASS after adding setup fixtures and expanding coverage.

- [ ] **Step 5: Expand tests**

Add tests for approve, revise, defer, self-review warning, and version completion.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/test_services_review.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/review.py tests/unit/test_services_review.py
uv run ruff check app/services/review.py tests/unit/test_services_review.py
uv run ruff format app/services/review.py tests/unit/test_services_review.py
git commit -m "feat(task-15): review service with approve, revise, defer (C-19)"
```

---

### Task 3: Create review router and register it

**Files:**
- Create: `app/api/routers/review.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_routers_review.py`

**Interfaces:**
- Consumes: `approve_domain`, `revise_and_approve`, `defer_domain` from `app.services.review`.
- Produces: `POST /domains/{code}/approve`, `POST /domains/{code}/revise`, `POST /domains/{code}/defer`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_routers_review.py` with a test that imports the new router.

```python
from fastapi.testclient import TestClient


def test_approve_requires_auth(client):
    response = client.post("/domains/AC/approve")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_routers_review.py -v`
Expected: 404 or import error.

- [ ] **Step 3: Write minimal implementation**

Create `app/api/routers/review.py`:

```python
"""Review workflow API router (Task 15)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user
from app.exceptions import AuthorizationError
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.review import approve_domain, defer_domain, revise_and_approve

router = APIRouter()


@router.post("/domains/{code}/approve")
async def approve_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """Approve a submitted domain."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await approve_domain(db, reviewer_id=user["id"], code=code)


@router.post("/domains/{code}/revise")
async def revise_domain_endpoint(
    request: Request,
    code: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    llm: Any | None = None,
) -> dict:
    """Revise the compiled narrative and immediately approve the domain."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await revise_and_approve(
        db,
        reviewer_id=user["id"],
        code=code,
        revision_prompt=payload["revision_prompt"],
        llm=llm,
    )


@router.post("/domains/{code}/defer")
async def defer_domain_endpoint(
    request: Request,
    code: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """Defer a submitted domain back to the contributor."""
    if authorization is None:
        raise AuthorizationError("Authorization header required", code="unauthorized")
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await defer_domain(db, reviewer_id=user["id"], code=code)
```

Modify `app/main.py` to import and register `review_router` alongside `compilation_router`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_routers_review.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routers/review.py app/main.py tests/unit/test_routers_review.py
uv run ruff check .
uv run ruff format .
git commit -m "feat(task-15): review endpoints approve, revise, defer"
```

---

### Task 4: Add notification templates

**Files:**
- Modify: `app/services/notification_templates.py`
- Test: `tests/unit/test_notification_templates.py`

- [ ] **Step 1: Add templates**

Add to `TEMPLATES` in `app/services/notification_templates.py`:

```python
    "domain_approved": (
        "A WISP domain has been approved",
        "The {domain_name} domain has been approved.",
    ),
    "domain_revised_and_approved": (
        "A WISP domain has been revised and approved",
        "The {domain_name} domain has been revised and approved.",
    ),
    "domain_deferred": (
        "A WISP domain needs more information",
        "The {domain_name} domain has been returned for more information.",
    ),
    "wisp_complete": (
        "Your WISP is complete",
        "All 14 domains have been approved. Your WISP is complete.",
    ),
```

Note: `wisp_complete` subject/body do not need a placeholder.

- [ ] **Step 2: Add unit tests**

Add render tests to `tests/unit/test_notification_templates.py`.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/unit/test_notification_templates.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/notification_templates.py tests/unit/test_notification_templates.py
git commit -m "feat(task-15): review workflow notification templates"
```

---

### Task 5: BDD scenarios and step definitions

**Files:**
- Create: `features/review-workflow.feature`
- Modify: `tests/steps/test_review_workflow.py`
- Modify: `tests/steps/conftest.py`

**Important:** Feature file changes require explicit human approval per AGENTS.md.

- [ ] **Step 1: Create feature file**

Create `features/review-workflow.feature` with REVW-01..05 scenarios as described in the design spec.

- [ ] **Step 2: Add `review_router` to BDD app fixture**

In `tests/steps/conftest.py`, import and mount `review_router`.

- [ ] **Step 3: Write step definitions**

Modify `tests/steps/test_review_workflow.py` to define:

- `Given a submitted domain "{code}"`
- `Given all 14 domains are submitted for "{email}"`
- `When the reviewer approves domain "{code}"`
- `When the reviewer revises domain "{code}" with prompt "{prompt}"`
- `When the reviewer defers domain "{code}"`
- `When the reviewer approves the last domain`
- `Then the compiled answer narrative contains "{text}"`
- `Then the response includes a self-review warning`
- `Then the WISP version status is "{status}"`
- `Then the admin receives a "{kind}" notification`

Reuse existing `given_compiled_domain` and `when_user_submits_domain` from `test_contributor_questionnaire.py` or move shared helpers to `common_steps.py`.

- [ ] **Step 4: Run BDD tests**

Run: `uv run pytest tests/steps/test_review_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Run full BDD suite**

Run: `uv run pytest tests/steps -q`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add features/review-workflow.feature tests/steps/test_review_workflow.py tests/steps/conftest.py
uv run ruff check .
uv run ruff format .
git commit -m "feat(task-15): BDD scenarios REVW-01..05 for review workflow"
```

---

### Task 6: Frontend Playwright smoke test

**Files:**
- Create: `frontend/e2e/review-workflow.spec.ts`

- [ ] **Step 1: Add API smoke test**

Create `frontend/e2e/review-workflow.spec.ts` extending the compilation flow: admin assigns a domain, contributor answers/compiles/submits, reviewer approves, asserts approved status and contributor notification.

- [ ] **Step 2: Run Playwright test**

Start backend with `LLM_PROVIDER=fake` and run:

```bash
cd frontend
npx playwright test e2e/review-workflow.spec.ts --config=playwright.manual.config.ts
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/review-workflow.spec.ts
git commit -m "test(task-15): Playwright review workflow smoke"
```

---

### Task 7: Verification and traceability

- [ ] **Step 1: Run full backend test suite**

Run: `uv run pytest tests/ -q`
Expected: PASS

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean

- [ ] **Step 3: Update TESTPLAN.md**

Mark REVW-01..05 as green in the traceability matrix.

- [ ] **Step 4: Commit**

```bash
git add TESTPLAN.md
git commit -m "docs(task-15): TESTPLAN green for REVW-01..05"
```

## Self-Review

- Spec coverage: REVW-01 (approve) in Task 2, 3, 5. REVW-02 (revise) in Task 1, 2, 5. REVW-03 (defer) in Task 2, 3, 5. REVW-04 (self-review warning) in Task 2/3 responses. REVW-05 (version completion) in Task 2 `_maybe_complete_version`.
- Placeholder scan: all steps include concrete code/commands; no TBD or "add appropriate".
- Type consistency: `approve_domain`, `revise_and_approve`, `defer_domain` signatures match router usage; `RevisionCrew` follows `CompilerCrew` pattern.
