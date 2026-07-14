# Task 14 — Compilation and Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the contributor-side compile and submit endpoints that turn a fully answered domain into a `CompiledAnswer` and transition the domain to `in_review` (C-12).

**Architecture:** A thin `compilation.py` service enforces preconditions and delegates narrative generation to a `CompilerCrew`. The router is mounted without prefix alongside the existing questionnaire router. Existing `answers.get_domain_progress` already computes `submit_ready`, so submit reuses that logic.

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
| `app/crews/compiler_crew.py` | New. Builds prompt, calls LLM, returns narrative. |
| `app/services/compilation.py` | New. `compile_domain` and `submit_domain` business rules. |
| `app/api/routers/compilation.py` | New. `POST /domains/{code}/compile` and `POST /domains/{code}/submit`. |
| `app/main.py` | Modify. Register `compilation_router`. |
| `app/services/notification_templates.py` | Modify. Add `domain_submitted` template. |
| `features/contributor-questionnaire.feature` | Modify (human approval required). Add QSTN-02 and QSTN-03 scenarios. |
| `tests/unit/test_compiler_crew.py` | New. Unit tests for `CompilerCrew`. |
| `tests/unit/test_services_compilation.py` | New. Unit tests for `compile_domain` and `submit_domain`. |
| `tests/unit/test_routers_compilation.py` | New. Router-level tests. |
| `tests/steps/test_contributor_questionnaire.py` | Modify. Add step definitions for QSTN-02 and QSTN-03. |
| `frontend/e2e/compilation.spec.ts` | New. Playwright API smoke test. |
| `TESTPLAN.md` | Modify. Update matrix statuses. |

---

### Task 1: Create `CompilerCrew`

**Files:**
- Create: `app/crews/compiler_crew.py`
- Test: `tests/unit/test_compiler_crew.py`

**Interfaces:**
- Consumes: `create_llm` from `app.ai.llm_factory`, `CrewBase` from `app.ai.crew_base`.
- Produces: `CompilerCrew(db, domain_code, domain_name, conversation, llm=None).compile() -> str`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.ai.fakes import FakeLLM
from app.crews.compiler_crew import CompilerCrew


@pytest.mark.asyncio
async def test_compiler_crew_returns_narrative():
    crew = CompilerCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        conversation=[
            {
                "question": "Do you restrict physical access?",
                "answer": "yes",
                "followups": [
                    {"text": "How do you badge visitors?", "response": "front desk issues temporary badges"}
                ],
            }
        ],
        llm=FakeLLM(default="We restrict physical access and badge visitors at the front desk."),
    )
    result = await crew.compile()
    assert isinstance(result, str)
    assert "badge" in result.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_compiler_crew.py -v`
Expected: `ModuleNotFoundError: No module named 'app.crews.compiler_crew'`

- [ ] **Step 3: Write minimal implementation**

Create `app/crews/compiler_crew.py`:

```python
"""CrewAI crew that compiles a domain conversation into a narrative answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


class CompilerCrew(CrewBase):
    """Compile a domain's questions, answers, and follow-up responses."""

    def __init__(
        self,
        db: "TenantDB" | None,
        *,
        domain_code: str,
        domain_name: str,
        conversation: list[dict[str, Any]],
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.conversation = conversation
        self.llm = llm or create_llm()

    async def compile(self) -> str:
        """Return a single WISP narrative paragraph for the domain."""
        return await self.run_with_retry(self._compile_once, max_retries=1)

    async def _compile_once(self) -> str:
        prompt = self._build_prompt()
        raw = await self._call_llm(prompt)
        return raw.strip()

    def _build_prompt(self) -> str:
        lines = [f"Domain: {self.domain_name} ({self.domain_code})"]
        lines.append("Write a single professional paragraph for a Written Information Security Program that summarizes the following contributor input.")
        for item in self.conversation:
            lines.append(f"Question: {item['question']}")
            lines.append(f"Answer: {item['answer']}")
            for fu in item.get("followups", []):
                lines.append(f"Follow-up: {fu['text']}")
                lines.append(f"Response: {fu['response']}")
        lines.append("Return only the paragraph, with no headings or lists.")
        return "\n\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        result = self.llm.call(prompt)
        if isinstance(result, str):
            return result
        raise RuntimeError("LLM did not return a string response")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_compiler_crew.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/crews/compiler_crew.py tests/unit/test_compiler_crew.py
uv run ruff check app/crews/compiler_crew.py tests/unit/test_compiler_crew.py
uv run ruff format app/crews/compiler_crew.py tests/unit/test_compiler_crew.py
git commit -m "feat(task-14): CompilerCrew for domain narrative (C-19)"
```

---

### Task 2: Create compilation service

**Files:**
- Create: `app/services/compilation.py`
- Test: `tests/unit/test_services_compilation.py`

**Interfaces:**
- Consumes: `TenantDB`, `CompilerCrew`, `get_domain_progress` from `app.services.answers`, `notify` and `audit` from `app.services.notifications` / `app.services.audit`.
- Produces: `compile_domain(db, *, contributor_id, code, llm=None) -> dict` and `submit_domain(db, *, contributor_id, code) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_services_compilation.py`:

```python
import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError, NotFoundError
from app.services.compilation import compile_domain, submit_domain


@pytest.fixture
async def db(tmp_path):
    return await init_tenant_db(str(tmp_path), "palmetto")


@pytest.mark.asyncio
async def test_compile_domain_requires_answers(db):
    with pytest.raises(ConflictError):
        await compile_domain(db, contributor_id=1, code="AC")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_services_compilation.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.compilation'`

- [ ] **Step 3: Write minimal implementation**

Create `app/services/compilation.py`:

```python
"""Compilation and submission service (Task 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.crews.compiler_crew import CompilerCrew
from app.db.tenant import TenantDB
from app.exceptions import AuthorizationError, ConflictError, ExternalServiceError, NotFoundError
from app.services.answers import get_domain_progress
from app.services.audit import audit
from app.services.notifications import notify


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def compile_domain(
    db: TenantDB,
    *,
    contributor_id: int,
    code: str,
    llm: Any | None = None,
) -> dict:
    """Compile a domain narrative if all enabled questions are answered."""
    domain = await _resolve_domain(db, code)
    if domain["contributor_id"] != contributor_id:
        raise AuthorizationError("domain not assigned to this user", code="forbidden")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError("domain is read-only", code="domain_read_only")

    questions = await _load_answered_questions(db, domain_id=domain["id"], contributor_id=contributor_id)

    conversation: list[dict[str, Any]] = []
    for q in questions:
        item = {
            "question": q["text"],
            "answer": "skipped" if q["answer"]["skipped"] else q["answer"]["value"],
            "followups": [
                {"text": f["text"], "response": f.get("response_text") or ""}
                for f in q["answer"].get("followups", [])
            ],
        }
        conversation.append(item)

    crew = CompilerCrew(
        db,
        domain_code=code,
        domain_name=domain["name"],
        conversation=conversation,
        llm=llm,
    )
    try:
        narrative = await crew.compile()
    except Exception as exc:
        raise ExternalServiceError("compilation failed; please retry", code="llm_unavailable") from exc

    await db.execute(
        """
        INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at)
        VALUES (?, ?, ?)
        ON CONFLICT(domain_id) DO UPDATE SET
            narrative_text=excluded.narrative_text,
            compiled_at=excluded.compiled_at
        """,
        (domain["id"], narrative, _now()),
    )
    await audit(
        db,
        actor_user_id=contributor_id,
        event_type="domain_compiled",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await db.commit()

    return {"domain_id": domain["id"], "narrative_text": narrative, "compiled_at": _now()}


async def submit_domain(
    db: TenantDB,
    *,
    contributor_id: int,
    code: str,
) -> dict:
    """Submit a compiled domain for reviewer approval."""
    domain = await _resolve_domain(db, code)
    if domain["contributor_id"] != contributor_id:
        raise AuthorizationError("domain not assigned to this user", code="forbidden")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError("domain is already submitted or approved", code="domain_already_submitted")

    progress = await get_domain_progress(db, user_id=contributor_id, code=code)
    if not progress["submit_ready"]:
        raise ConflictError("domain is not ready for submission", code="domain_not_ready")

    compiled = await db.fetchone(
        "SELECT id FROM compiled_answers WHERE domain_id = ?",
        (domain["id"],),
    )
    if compiled is None:
        raise ConflictError("domain has not been compiled", code="domain_not_compiled")

    await db.execute(
        "UPDATE domains SET status = 'in_review' WHERE id = ?",
        (domain["id"],),
    )
    await audit(
        db,
        actor_user_id=contributor_id,
        event_type="domain_submitted",
        subject=f"domain:{code}",
        detail="",
        commit=False,
    )
    await notify(
        db,
        user_id=domain["reviewer_id"],
        kind="domain_submitted",
        payload={"domain_name": domain["name"]},
        channel="in_app",
        commit=False,
    )
    await db.commit()

    return {
        "domain_id": domain["id"],
        "code": code,
        "name": domain["name"],
        "status": "in_review",
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


async def _load_answered_questions(db: TenantDB, *, domain_id: int, contributor_id: int) -> list[dict[str, Any]]:
    questions = await db.fetchall(
        "SELECT * FROM questions WHERE domain_id = ? AND enabled = 1 ORDER BY position",
        (domain_id,),
    )
    result: list[dict[str, Any]] = []
    for q in questions:
        answer = await db.fetchone(
            "SELECT * FROM answers WHERE question_id = ? AND contributor_id = ?",
            (q["id"], contributor_id),
        )
        if answer is None:
            raise ConflictError("not all questions are answered", code="questions_unanswered")
        answer_dict = dict(answer)
        if answer_dict["skipped"]:
            raise ConflictError("skipped questions block compilation", code="question_skipped")
        if answer_dict["followups_state"] == "pending":
            raise ConflictError("follow-ups pending", code="followups_pending")

        from app.services import followups as followups_service

        answer_dict["followups"] = await followups_service.get_followups_for_answer(
            db, answer_id=answer_dict["id"]
        )
        result.append({"text": q["text"], "answer": answer_dict})
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_services_compilation.py -v`
Expected: PASS after adding setup fixtures below.

- [ ] **Step 5: Expand tests for happy path and skip/ready checks**

Add to `tests/unit/test_services_compilation.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_compile_and_submit_flow(db):
    # seed user, version, domain, assignment, question, answer
    await db.execute(
        "INSERT INTO users (email, password_hash, roles, status, totp_secret, totp_enrolled) VALUES (?, ?, ?, ?, ?, ?)",
        ("c@test.com", "x", '["contributor"]', "active", "s", 1),
    )
    contributor_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@test.com",)))["id"]
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
        (domain_id, contributor_id, contributor_id),
    )
    await db.execute(
        "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) VALUES (?, ?, ?, ?, ?, ?)",
        (domain_id, "Q1", "yes_no", "seeded", 1, 1),
    )
    question_id = (await db.fetchone("SELECT id FROM questions"))["id"]
    await db.execute(
        "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) VALUES (?, ?, ?, ?, ?)",
        (question_id, contributor_id, "yes", 0, "complete"),
    )
    await db.commit()

    compiled = await compile_domain(db, contributor_id=contributor_id, code="AC", llm=FakeLLM(default="Narrative text."))
    assert compiled["narrative_text"]

    submitted = await submit_domain(db, contributor_id=contributor_id, code="AC")
    assert submitted["status"] == "in_review"
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/test_services_compilation.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/compilation.py tests/unit/test_services_compilation.py
uv run ruff check app/services/compilation.py tests/unit/test_services_compilation.py
uv run ruff format app/services/compilation.py tests/unit/test_services_compilation.py
git commit -m "feat(task-14): compilation and submission service (C-12, C-19)"
```

---

### Task 3: Create compilation router and register it

**Files:**
- Create: `app/api/routers/compilation.py`
- Modify: `app/main.py`
- Test: `tests/unit/test_routers_compilation.py`

**Interfaces:**
- Consumes: `compile_domain` and `submit_domain` from `app.services.compilation`.
- Produces: `POST /domains/{code}/compile` and `POST /domains/{code}/submit`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_routers_compilation.py` with a test that imports and calls the endpoints via `TestClient`.

```python
from fastapi.testclient import TestClient


def test_compile_requires_auth(client):
    response = client.post("/domains/AC/compile")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_routers_compilation.py -v`
Expected: 404 because router is not registered, or failure to import.

- [ ] **Step 3: Write minimal implementation**

Create `app/api/routers/compilation.py`:

```python
"""Compilation and submission API router (Task 14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.compilation import compile_domain, submit_domain

router = APIRouter()


@router.post("/domains/{code}/compile")
async def compile_domain_endpoint(
    request: Request,
    code: str,
    authorization: str = Header(...),
    llm: Any | None = None,
) -> dict:
    """Compile the contributor's answers into a domain narrative."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await compile_domain(db, contributor_id=user["id"], code=code, llm=llm)


@router.post("/domains/{code}/submit")
async def submit_domain_endpoint(
    request: Request,
    code: str,
    authorization: str = Header(...),
) -> dict:
    """Submit a compiled domain for reviewer approval."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await submit_domain(db, contributor_id=user["id"], code=code)
```

Modify `app/main.py` to register the router:

```python
from app.api.routers.compilation import router as compilation_router
```

Add:

```python
app.include_router(compilation_router, tags=["compilation"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_routers_compilation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routers/compilation.py app/main.py tests/unit/test_routers_compilation.py
uv run ruff check .
uv run ruff format .
git commit -m "feat(task-14): compile and submit endpoints (C-12)"
```

---

### Task 4: Add notification template

**Files:**
- Modify: `app/services/notification_templates.py`

- [ ] **Step 1: Add `domain_submitted` template**

```python
    "domain_submitted": (
        "A WISP domain is ready for review",
        "The {domain_name} domain has been submitted for review.",
    ),
```

- [ ] **Step 2: Run notification template tests**

Run: `uv run pytest tests/unit/test_notification_templates.py -v` (create if absent)
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/services/notification_templates.py
git commit -m "feat(task-14): domain_submitted notification template"
```

---

### Task 5: BDD scenarios and step definitions

**Files:**
- Modify: `features/contributor-questionnaire.feature`
- Modify: `tests/steps/test_contributor_questionnaire.py`

**Important:** Feature file changes require explicit human approval per AGENTS.md.

- [ ] **Step 1: Add QSTN-02 and QSTN-03 scenarios to feature file**

Append to `features/contributor-questionnaire.feature`:

```gherkin
  Scenario: QSTN-02 AI compiles the domain final answer
    Given a fully answered domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" compiles domain "AC"
    Then the compiled answer narrative is non-empty
    And a "domain_compiled" audit event exists for domain "AC"

  Scenario: QSTN-03 Contributor submits the domain for review
    Given a compiled domain "AC" for "contributor@palmetto.app.wisp.llc"
    When "contributor@palmetto.app.wisp.llc" submits domain "AC"
    Then the domain "AC" status is "in_review"
    And the reviewer receives a "domain_submitted" notification
```

- [ ] **Step 2: Add step definitions**

Add to `tests/steps/test_contributor_questionnaire.py`:

```python
import sqlite3

from pytest_bdd import given, parsers, scenario, then, when


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-02 AI compiles the domain final answer",
)
def test_qstn02_ai_compiles_domain():
    pass


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-03 Contributor submits the domain for review",
)
def test_qstn03_contributor_submits_domain():
    pass


@given(parsers.parse('a fully answered domain "{code}" for "{email}"'))
def given_fully_answered_domain(client, context, data_dir, provisioned_tenant, code, email):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        # ensure assignment matches the user
        conn.execute("DELETE FROM domain_assignments WHERE domain_id = ?", (domain_id,))
        conn.execute(
            "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)",
            (domain_id, user_id, user_id),
        )
        conn.execute(
            "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) VALUES (?, ?, ?, ?, ?, ?)",
            (domain_id, "Fully answered question", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) VALUES (?, ?, ?, ?, ?)",
            (question_id, user_id, "yes", 0, "complete"),
        )
        conn.commit()
    finally:
        conn.close()


@given(parsers.parse('a compiled domain "{code}" for "{email}"'))
def given_compiled_domain(client, context, data_dir, provisioned_tenant, code, email):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        conn.execute("DELETE FROM domain_assignments WHERE domain_id = ?", (domain_id,))
        conn.execute(
            "INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id) VALUES (?, ?, ?)",
            (domain_id, user_id, user_id),
        )
        conn.execute(
            "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) VALUES (?, ?, ?, ?, ?, ?)",
            (domain_id, "Compiled question", "yes_no", "seeded", 1, 1),
        )
        question_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) VALUES (?, ?, ?, ?, ?)",
            (question_id, user_id, "yes", 0, "complete"),
        )
        conn.execute(
            "INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at) VALUES (?, ?, ?)",
            (domain_id, "Compiled narrative.", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()


@when(parsers.parse('"{email}" compiles domain "{code}"'))
def when_user_compiles_domain(client, context, email, code):
    response = client.post(
        f"/domains/{code}/compile",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["compile_response"] = response.json()


@when(parsers.parse('"{email}" submits domain "{code}"'))
def when_user_submits_domain(client, context, email, code):
    response = client.post(
        f"/domains/{code}/submit",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["submit_response"] = response.json()


@then("the compiled answer narrative is non-empty")
def then_compiled_narrative_non_empty(context):
    assert context["compile_response"]["narrative_text"]


@then(parsers.parse('a "{event_type}" audit event exists for domain "{code}"'))
def then_audit_event_for_domain(client, context, data_dir, provisioned_tenant, event_type, code):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = ? AND subject = ?",
            (event_type, f"domain:{code}"),
        )
        assert cur.fetchone()[0] >= 1
    finally:
        conn.close()


@then(parsers.parse('the domain "{code}" status is "{status}"'))
def then_domain_status(client, context, data_dir, provisioned_tenant, code, status):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT status FROM domains WHERE code = ?", (code,))
        assert cur.fetchone()[0] == status
    finally:
        conn.close()


@then(parsers.parse('the reviewer receives a "{kind}" notification'))
def then_reviewer_notification(client, context, data_dir, provisioned_tenant, kind):
    # reviewer is the same as contributor in these scenarios; use their token
    response = client.get(
        "/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    notifications = response.json()
    assert any(n["type"] == kind for n in notifications)
```

- [ ] **Step 3: Run BDD tests**

Run: `uv run pytest tests/steps/test_contributor_questionnaire.py -v -k "QSTN-02 or QSTN-03"`
Expected: PASS

- [ ] **Step 4: Run full BDD suite**

Run: `uv run pytest tests/steps -q`
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add features/contributor-questionnaire.feature tests/steps/test_contributor_questionnaire.py
uv run ruff check .
uv run ruff format .
git commit -m "feat(task-14): BDD scenarios QSTN-02/03 for compile and submit (C-12, C-19)"
```

---

### Task 6: Frontend Playwright smoke test

**Files:**
- Create: `frontend/e2e/compilation.spec.ts`

- [ ] **Step 1: Add API smoke test**

```typescript
import { test, expect } from '@playwright/test';
import { tenantBase, signIn } from './helpers';

test('compile and submit a domain via API', async ({ request }) => {
  const token = await signIn(request, 'palmetto', 'contributor@palmetto.app.wisp.llc', 'SecurePass123!');
  const compile = await request.post(`${tenantBase('palmetto')}/domains/AC/compile`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(compile.ok()).toBeTruthy();
  const body = await compile.json();
  expect(body.narrative_text).toBeTruthy();

  const submit = await request.post(`${tenantBase('palmetto')}/domains/AC/submit`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(submit.ok()).toBeTruthy();
  const submitted = await submit.json();
  expect(submitted.status).toBe('in_review');
});
```

- [ ] **Step 2: Run Playwright test**

Run: `cd frontend && npx playwright test e2e/compilation.spec.ts`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/compilation.spec.ts
git commit -m "test(task-14): Playwright compile and submit smoke"
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

Mark QSTN-02 and QSTN-03 as green in the traceability matrix.

- [ ] **Step 4: Commit**

```bash
git add TESTPLAN.md
git commit -m "docs(task-14): TESTPLAN green for QSTN-02/03"
```

## Self-Review

- Spec coverage: QSTN-02 (compile) covered in Task 1–3, 5. QSTN-03 (submit) covered in Task 2–3, 5. C-12 enforced by service status checks. C-19 enforced by catching LLM exception and raising `ExternalServiceError` without state transition.
- Placeholder scan: all steps include concrete code/commands; no TBD or "add appropriate".
- Type consistency: `compile_domain` and `submit_domain` signatures match router usage; `CompilerCrew` follows `FollowUpCrew` pattern.
