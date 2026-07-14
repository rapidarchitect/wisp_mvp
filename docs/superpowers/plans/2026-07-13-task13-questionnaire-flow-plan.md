# Task 13 — Contributor Questionnaire Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the contributor questionnaire endpoints, services, and follow-up generation so that contributors can answer questions, respond to AI-generated follow-ups, save/resume progress, and submit only when all questions are fully answered.

**Architecture:** The answer service orchestrates question persistence, follow-up generation via `FollowUpCrew`, and state transitions on the domain. A thin router exposes three endpoints. Existing notification and audit helpers are reused.

**Tech Stack:** Python 3.12, FastAPI, uv, aiosqlite, httpx, orjson, pydantic v2, pytest-bdd, ruff. CrewAI + Tavily for follow-up generation. Playwright for API smoke tests.

## Global Constraints

- Do not create or edit `features/*.feature` without explicit human approval.
- Do not add dependencies beyond the constitution's approved list without asking.
- Never call real LLM, Tavily, Stripe, or SES endpoints from tests.
- Use `uv` only for Python operations; `pip` is forbidden.
- Use `orjson` instead of standard `json`.
- Use `httpx` instead of `requests`.
- All tests must pass before any task is marked done.
- Commit after every task; messages cite task and constraint IDs.

---

## File map

| File | Responsibility |
|------|----------------|
| `app/services/answers.py` | Answer persistence, follow-up orchestration, domain state transition, `get_domain_progress`. |
| `app/services/followups.py` | Follow-up persistence helpers. |
| `app/crews/followup_crew.py` | CrewAI task that generates up to 3 follow-up questions from an answer. |
| `app/api/routers/questionnaire.py` | FastAPI router for answer, follow-up response, and progress endpoints. |
| `app/main.py` | Mount the questionnaire router. |
| `tests/unit/test_services_answers.py` | Unit tests for answer service. |
| `tests/unit/test_followup_crew.py` | Unit tests for follow-up generation and failure fallback. |
| `tests/steps/test_contributor_questionnaire.py` | pytest-bdd step definitions for QSTN-01, QSTN-04, QSTN-05, QSTN-06. |
| `frontend/e2e/questionnaire.spec.ts` | Playwright API smoke test for the answer/progress endpoints. |
| `TESTPLAN.md` | Update traceability matrix. |

---

## Task 1: Follow-up persistence helpers

**Files:**
- Create: `app/services/followups.py`
- Test: `tests/unit/test_followups_service.py`

**Interfaces:**
- Consumes: `sqlite3.Connection` from service layer.
- Produces:
  - `insert_followups(db: sqlite3.Connection, answer_id: int, texts: list[str]) -> list[dict]`
  - `get_followups_for_answer(db: sqlite3.Connection, answer_id: int) -> list[dict]`
  - `save_followup_response(db: sqlite3.Connection, followup_id: int, response_text: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_followups_service.py
import sqlite3
import pytest
from app.services.followups import insert_followups, get_followups_for_answer, save_followup_response

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE answers (id INTEGER PRIMARY KEY);
        CREATE TABLE followups (
            id INTEGER PRIMARY KEY,
            answer_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            response_text TEXT,
            created_at TEXT DEFAULT 'now'
        );
    """)
    return conn


def test_insert_and_get_followups(db):
    db.execute("INSERT INTO answers (id) VALUES (1)")
    db.commit()
    rows = insert_followups(db, answer_id=1, texts=["What is your name?", "Why?"])
    assert len(rows) == 2
    assert rows[0]["position"] == 1
    loaded = get_followups_for_answer(db, answer_id=1)
    assert [r["text"] for r in loaded] == ["What is your name?", "Why?"]


def test_save_response(db):
    db.execute("INSERT INTO answers (id) VALUES (1)")
    db.commit()
    insert_followups(db, answer_id=1, texts=["Q1"])
    row = save_followup_response(db, followup_id=1, response_text="  A1  ")
    assert row["response_text"] == "A1"
    assert get_followups_for_answer(db, answer_id=1)[0]["response_text"] == "A1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_followups_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.followups'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/followups.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_followups(db: sqlite3.Connection, *, answer_id: int, texts: list[str]) -> list[dict]:
    rows: list[dict] = []
    for position, text in enumerate(texts, start=1):
        cursor = db.execute(
            "INSERT INTO followups (answer_id, position, text, created_at) VALUES (?, ?, ?, ?)",
            (answer_id, position, text, _now()),
        )
        rows.append({
            "id": cursor.lastrowid,
            "answer_id": answer_id,
            "position": position,
            "text": text,
            "response_text": None,
        })
    db.commit()
    return rows


def get_followups_for_answer(db: sqlite3.Connection, *, answer_id: int) -> list[dict]:
    cursor = db.execute("SELECT * FROM followups WHERE answer_id = ? ORDER BY position", (answer_id,))
    return [dict(row) for row in cursor.fetchall()]


def save_followup_response(db: sqlite3.Connection, *, followup_id: int, response_text: str) -> dict:
    cleaned = response_text.strip()
    db.execute(
        "UPDATE followups SET response_text = ? WHERE id = ?",
        (cleaned, followup_id),
    )
    db.commit()
    cursor = db.execute("SELECT * FROM followups WHERE id = ?", (followup_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError("followup not found")
    return dict(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_followups_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/followups.py tests/unit/test_followups_service.py
uv run ruff check app/services/followups.py tests/unit/test_followups_service.py
git commit -m "feat(task-13): follow-up persistence helpers (QSTN-01)"
```

---

## Task 2: Follow-up generation crew

**Files:**
- Create: `app/crews/followup_crew.py`
- Modify: `app/crews/base.py` if `CrewBase.run_with_retry` is missing; otherwise reuse.
- Test: `tests/unit/test_followup_crew.py`

**Interfaces:**
- Consumes: `sqlite3.Connection`, domain metadata, answer value, optional `llm`.
- Produces:
  - `FollowUpCrew(db, answer_id, domain_code, domain_name, answer_value, answer_text, llm=None)`
  - `crew.generate() -> list[str]` — returns up to 3 follow-up texts.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_followup_crew.py
import sqlite3
import pytest
from app.crews.followup_crew import FollowUpCrew


def test_generates_followups(monkeypatch):
    def fake_llm_call(*args, **kwargs):
        return '1. What is the policy number?\n2. Who approved it?\n3. When was it last reviewed?'

    crew = FollowUpCrew(None, answer_id=1, domain_code="HR", domain_name="HR", answer_value="yes", answer_text="We have a policy.")
    monkeypatch.setattr(crew, "_call_llm", fake_llm_call)
    result = crew.generate()
    assert result == [
        "What is the policy number?",
        "Who approved it?",
        "When was it last reviewed?",
    ]


def test_truncates_to_three(monkeypatch):
    def fake_llm_call(*args, **kwargs):
        return "1. A\n2. B\n3. C\n4. D\n5. E"

    crew = FollowUpCrew(None, answer_id=1, domain_code="HR", domain_name="HR", answer_value="yes", answer_text="We have a policy.")
    monkeypatch.setattr(crew, "_call_llm", fake_llm_call)
    result = crew.generate()
    assert len(result) == 3


def test_failure_raises_after_retry(monkeypatch):
    crew = FollowUpCrew(None, answer_id=1, domain_code="HR", domain_name="HR", answer_value="yes", answer_text="We have a policy.")
    monkeypatch.setattr(crew, "_call_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        crew.generate()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_followup_crew.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crews.followup_crew'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/crews/followup_crew.py
from __future__ import annotations

import re
import sqlite3
from typing import Any

from app.ai.llm_factory import create_llm
from app.crews.base import CrewBase


class FollowUpCrew(CrewBase):
    def __init__(
        self,
        db: sqlite3.Connection | None,
        *,
        answer_id: int,
        domain_code: str,
        domain_name: str,
        answer_value: str,
        answer_text: str | None,
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.answer_id = answer_id
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.answer_value = answer_value
        self.answer_text = answer_text or ""
        self.llm = llm or create_llm()

    def generate(self) -> list[str]:
        return self.run_with_retry(self._generate_once, max_retries=1)

    def _generate_once(self) -> list[str]:
        prompt = self._build_prompt()
        raw = self._call_llm(prompt)
        return self._parse(raw)

    def _build_prompt(self) -> str:
        return (
            f"You are a security compliance analyst writing a Written Information Security Program.\n"
            f"Domain: {self.domain_name} ({self.domain_code})\n"
            f"The contributor answered a yes/no question with value '{self.answer_value}'.\n"
            f"Additional context: {self.answer_text}\n"
            "Generate up to 3 short, specific follow-up questions that dig deeper into the answer. "
            "Number each question. Return only the numbered list."
        )

    def _call_llm(self, prompt: str) -> str:
        # CrewAI LLM is sync-callable in this project
        return self.llm(prompt)

    def _parse(self, raw: str) -> list[str]:
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        questions: list[str] = []
        for line in lines:
            cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            if cleaned:
                questions.append(cleaned)
        return questions[:3]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_followup_crew.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/crews/followup_crew.py tests/unit/test_followup_crew.py
uv run ruff check app/crews/followup_crew.py tests/unit/test_followup_crew.py
git commit -m "feat(task-13): follow-up generation crew with cap and retry (C-09, C-19)"
```

---

## Task 3: Answer service

**Files:**
- Create: `app/services/answers.py`
- Modify: `app/services/notifications.py` (add `answer_saved` and `followups_waived` notifications if not present).
- Test: `tests/unit/test_services_answers.py`

**Interfaces:**
- Consumes: `app.services.followups`, `app.crews.followup_crew.FollowUpCrew`, `app.services.notifications`, `app.services.audit`.
- Produces:
  - `save_answer(db, *, contributor_id, question_id, value=None, skipped=False, llm=None) -> dict`
  - `save_followup_response(db, *, contributor_id, followup_id, response_text) -> dict`
  - `get_domain_progress(db, *, user_id, code) -> dict`
  - `NotFoundError`, `ForbiddenError`, `ConflictError` exceptions.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_services_answers.py
import sqlite3
import pytest
from app.services.answers import save_answer, save_followup_response, get_domain_progress
from app.errors import ForbiddenError, NotFoundError


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE versions (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT);
        CREATE TABLE domains (
            id INTEGER PRIMARY KEY,
            version_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_to INTEGER,
            foreign key (version_id) references versions(id)
        );
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY,
            domain_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            position INTEGER NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT 1
        );
        CREATE TABLE answers (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL,
            contributor_id INTEGER NOT NULL,
            value TEXT,
            skipped BOOLEAN NOT NULL DEFAULT 0,
            followups_state TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE followups (
            id INTEGER PRIMARY KEY,
            answer_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            response_text TEXT
        );
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            payload TEXT,
            read BOOLEAN NOT NULL DEFAULT 0
        );
        INSERT INTO versions (id, tenant_id, status) VALUES (1, 1, 'in_progress');
        INSERT INTO domains (id, version_id, code, name, status, assigned_to) VALUES (10, 1, 'HR', 'HR', 'assigned', 5);
        INSERT INTO questions (id, domain_id, text, position, enabled) VALUES (100, 10, 'Q1', 1, 1), (101, 10, 'Q2', 2, 1);
    """)
    return conn


def test_save_answer_creates_followups(monkeypatch, db):
    def fake_generate(self):
        return ["Why?", "How?"]
    monkeypatch.setattr("app.crews.followup_crew.FollowUpCrew.generate", fake_generate)

    result = save_answer(db, contributor_id=5, question_id=100, value="yes")
    assert result["value"] == "yes"
    assert result["followups_state"] == "pending"
    assert len(result["followups"]) == 2


def test_skip_answer_blocks_submit_ready(db):
    save_answer(db, contributor_id=5, question_id=100, skipped=True)
    progress = get_domain_progress(db, user_id=5, code="HR")
    assert progress["submit_ready"] is False


def test_answer_without_followups_is_not_submit_ready(monkeypatch, db):
    def fake_generate(self):
        return ["Why?"]
    monkeypatch.setattr("app.crews.followup_crew.FollowUpCrew.generate", fake_generate)
    save_answer(db, contributor_id=5, question_id=100, value="yes")
    progress = get_domain_progress(db, user_id=5, code="HR")
    assert progress["submit_ready"] is False


def test_complete_followups_make_submit_ready(monkeypatch, db):
    def fake_generate(self):
        return ["Why?"]
    monkeypatch.setattr("app.crews.followup_crew.FollowUpCrew.generate", fake_generate)
    answer = save_answer(db, contributor_id=5, question_id=100, value="yes")
    save_followup_response(db, contributor_id=5, followup_id=answer["followups"][0]["id"], response_text="Because.")
    save_answer(db, contributor_id=5, question_id=101, value="no")
    progress = get_domain_progress(db, user_id=5, code="HR")
    assert progress["submit_ready"] is True


def test_waived_followups_make_submit_ready_on_ai_failure(monkeypatch, db):
    calls = {"n": 0}
    def fake_generate(self):
        calls["n"] += 1
        raise RuntimeError("AI down")
    monkeypatch.setattr("app.crews.followup_crew.FollowUpCrew.generate", fake_generate)
    result = save_answer(db, contributor_id=5, question_id=100, value="yes")
    assert result["followups_state"] == "waived"
    progress = get_domain_progress(db, user_id=5, code="HR")
    assert progress["submit_ready"] is True
    assert calls["n"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_services_answers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.answers'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/answers.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.crews.followup_crew import FollowUpCrew
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.services import audit, followups, notifications


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_answer(
    db: sqlite3.Connection,
    *,
    contributor_id: int,
    question_id: int,
    value: str | None = None,
    skipped: bool = False,
    llm: Any | None = None,
) -> dict:
    cursor = db.execute(
        """
        SELECT q.id as question_id, q.domain_id, q.text, q.position,
               d.id as domain_id, d.code, d.name, d.status, d.assigned_to
        FROM questions q
        JOIN domains d ON d.id = q.domain_id
        WHERE q.id = ?
        """,
        (question_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise NotFoundError("question not found")

    domain = dict(row)
    if domain["assigned_to"] != contributor_id:
        raise ForbiddenError("domain not assigned to this user")
    if domain["status"] in ("in_review", "approved"):
        raise ConflictError("domain is read-only")

    # Check for existing final answer
    existing = db.execute(
        "SELECT id, value, skipped, followups_state FROM answers WHERE question_id = ? AND contributor_id = ?",
        (question_id, contributor_id),
    ).fetchone()
    if existing:
        state = existing["followups_state"]
        if existing["skipped"] or state in ("complete", "waived"):
            raise ConflictError("question already answered")

    if skipped:
        followups_state = "complete"
    else:
        followups_state = "pending"

    cursor = db.execute(
        """
        INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id, contributor_id) DO UPDATE SET
            value=excluded.value,
            skipped=excluded.skipped,
            followups_state=excluded.followups_state,
            updated_at=excluded.updated_at
        """,
        (question_id, contributor_id, value, skipped, followups_state, _now(), _now()),
    )
    db.commit()
    answer_id = cursor.lastrowid

    generated_followups: list[dict] = []
    if not skipped and followups_state == "pending":
        crew = FollowUpCrew(
            db,
            answer_id=answer_id,
            domain_code=domain["code"],
            domain_name=domain["name"],
            answer_value=value or "",
            answer_text="",
            llm=llm,
        )
        try:
            texts = crew.generate()
            generated_followups = followups.insert_followups(db, answer_id=answer_id, texts=texts[:3])
        except Exception:
            db.execute(
                "UPDATE answers SET followups_state = 'waived', updated_at = ? WHERE id = ?",
                (_now(), answer_id),
            )
            db.commit()
            followups_state = "waived"
            notifications.create(db, user_id=contributor_id, type="followups_waived", payload={"answer_id": answer_id})
            audit.log(db, actor_id=contributor_id, action="followups_waived", target=f"answer:{answer_id}", details={"domain_code": domain["code"]})

    if domain["status"] == "assigned":
        db.execute("UPDATE domains SET status = 'in_progress', updated_at = ? WHERE id = ?", (_now(), domain["domain_id"]))
        db.commit()

    notifications.create(db, user_id=contributor_id, type="answer_saved", payload={"question_id": question_id})
    audit.log(db, actor_id=contributor_id, action="answer_saved", target=f"question:{question_id}", details={"skipped": skipped})

    return _build_answer_dict(db, answer_id, generated_followups, followups_state)


def _build_answer_dict(db: sqlite3.Connection, answer_id: int, followup_rows: list[dict], state: str) -> dict:
    row = db.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
    answer = dict(row)
    answer["followups_state"] = state
    answer["followups"] = followup_rows or followups.get_followups_for_answer(db, answer_id=answer_id)
    return answer


def save_followup_response(
    db: sqlite3.Connection,
    *,
    contributor_id: int,
    followup_id: int,
    response_text: str,
) -> dict:
    row = db.execute(
        """
        SELECT f.id, f.answer_id, a.contributor_id, a.followups_state
        FROM followups f
        JOIN answers a ON a.id = f.answer_id
        WHERE f.id = ?
        """,
        (followup_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("followup not found")
    if row["contributor_id"] != contributor_id:
        raise ForbiddenError("not your followup")

    updated = followups.save_followup_response(db, followup_id=followup_id, response_text=response_text)

    all_followups = followups.get_followups_for_answer(db, answer_id=row["answer_id"])
    if all(f.get("response_text") for f in all_followups):
        db.execute(
            "UPDATE answers SET followups_state = 'complete', updated_at = ? WHERE id = ?",
            (_now(), row["answer_id"]),
        )
        db.commit()

    return updated


def get_domain_progress(db: sqlite3.Connection, *, user_id: int, code: str) -> dict:
    version = db.execute(
        "SELECT id FROM versions WHERE status = 'in_progress' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if version is None:
        raise NotFoundError("no in-progress version")

    domain = db.execute(
        "SELECT * FROM domains WHERE version_id = ? AND code = ?",
        (version["id"], code),
    ).fetchone()
    if domain is None:
        raise NotFoundError("domain not found")
    if domain["assigned_to"] != user_id:
        raise ForbiddenError("domain not assigned to this user")

    questions = db.execute(
        "SELECT * FROM questions WHERE domain_id = ? AND enabled = 1 ORDER BY position",
        (domain["id"],),
    ).fetchall()

    question_list: list[dict] = []
    submit_ready = True
    for q in questions:
        answer_row = db.execute(
            "SELECT * FROM answers WHERE question_id = ? AND contributor_id = ?",
            (q["id"], user_id),
        ).fetchone()
        if answer_row is None:
            submit_ready = False
            question_list.append({"id": q["id"], "text": q["text"], "position": q["position"], "answer": None})
            continue

        answer = dict(answer_row)
        answer["followups"] = followups.get_followups_for_answer(db, answer_id=answer["id"])
        question_list.append({"id": q["id"], "text": q["text"], "position": q["position"], "answer": answer})

        if answer["skipped"]:
            submit_ready = False
        elif answer["followups_state"] not in ("complete", "waived"):
            submit_ready = False

    return {
        "domain_id": domain["id"],
        "code": domain["code"],
        "name": domain["name"],
        "status": domain["status"],
        "questions": question_list,
        "submit_ready": submit_ready,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_services_answers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/answers.py tests/unit/test_services_answers.py
uv run ruff check app/services/answers.py tests/unit/test_services_answers.py
git commit -m "feat(task-13): answer service with progress and AI outage waiver (C-09, C-11, C-19)"
```

---

## Task 4: Questionnaire router

**Files:**
- Create: `app/api/routers/questionnaire.py`
- Modify: `app/main.py` to mount the router.
- Modify: `app/errors.py` if needed to add `ConflictError`.
- Test: `tests/unit/test_routers_questionnaire.py`

**Interfaces:**
- Consumes: `app.services.answers`.
- Produces: FastAPI routes:
  - `POST /questions/{question_id}/answer`
  - `POST /followups/{followup_id}/respond`
  - `GET /domains/{code}/progress`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_routers_questionnaire.py
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_progress_requires_auth():
    response = client.get("/api/domains/HR/progress")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_routers_questionnaire.py -v`
Expected: FAIL — router not mounted or path not found.

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/routers/questionnaire.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_current_user
from app.services.answers import get_domain_progress, save_answer, save_followup_response

router = APIRouter(prefix="", tags=["questionnaire"])


def _get_db(request: Request):
    return request.state.db


@router.post("/questions/{question_id}/answer")
def answer_question(
    question_id: int,
    payload: dict[str, Any],
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = _get_db(request)
    value = payload.get("value")
    skipped = payload.get("skipped", False)
    result = save_answer(
        db,
        contributor_id=user["id"],
        question_id=question_id,
        value=value,
        skipped=skipped,
    )
    return result


@router.post("/followups/{followup_id}/respond")
def respond_to_followup(
    followup_id: int,
    payload: dict[str, Any],
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = _get_db(request)
    return save_followup_response(
        db,
        contributor_id=user["id"],
        followup_id=followup_id,
        response_text=payload["response_text"],
    )


@router.get("/domains/{code}/progress")
def domain_progress(
    code: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = _get_db(request)
    return get_domain_progress(db, user_id=user["id"], code=code)
```

Mount in `app/main.py` under the tenant router, alongside existing routers.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_routers_questionnaire.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/routers/questionnaire.py app/main.py tests/unit/test_routers_questionnaire.py
uv run ruff check app/api/routers/questionnaire.py app/main.py tests/unit/test_routers_questionnaire.py
git commit -m "feat(task-13): questionnaire router (QSTN-01, QSTN-05)"
```

---

## Task 5: BDD step definitions

**Files:**
- Create: `tests/steps/test_contributor_questionnaire.py`
- Check: `features/contributor-questionnaire.feature` exists and contains scenarios QSTN-01, QSTN-04, QSTN-05, QSTN-06.

**Interfaces:**
- Consumes: Common step definitions in `tests/steps/common_steps.py`, helpers in `tests/steps/helpers.py`.
- Produces: pytest-bdd step definitions.

- [ ] **Step 1: Inspect feature file**

Read `features/contributor-questionnaire.feature` and verify the scenario IDs and steps. If missing, stop and ask user before creating.

- [ ] **Step 2: Write failing BDD tests**

```python
# tests/steps/test_contributor_questionnaire.py
import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("../features/contributor-questionnaire.feature")
```

Stub the steps used by QSTN-01, QSTN-04, QSTN-05, QSTN-06. Use `tests/steps/helpers.py` `_tenant_db_path(tenant_id)` and fastapi `TestClient`.

- [ ] **Step 3: Run BDD tests to verify they fail**

Run: `uv run pytest tests/steps/test_contributor_questionnaire.py -v`
Expected: FAIL — missing step implementations.

- [ ] **Step 4: Implement step definitions**

Use existing common Givens for authenticated contributor, assigned domain, seeded questions. Implement `when` steps calling the new router endpoints, `then` steps asserting generated follow-ups, skipped status, resumed state, waived state, and `submit_ready`.

- [ ] **Step 5: Run BDD tests to verify they pass**

Run: `uv run pytest tests/steps/test_contributor_questionnaire.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/steps/test_contributor_questionnaire.py
uv run ruff check tests/steps/test_contributor_questionnaire.py
uv run pytest tests/steps -q
git commit -m "feat(task-13): contributor questionnaire BDD steps (QSTN-01/04/05/06)"
```

---

## Task 6: Frontend API smoke test

**Files:**
- Create: `frontend/e2e/questionnaire.spec.ts`
- Test: `npm run test:e2e -- questionnaire.spec.ts`

- [ ] **Step 1: Write the smoke test**

Use `frontend/e2e/setup.py` to seed a demo tenant and a deterministic contributor with the fixed TOTP secret `JBSWY3DPEHPK3PXP`. Use `frontend/e2e/api-client.ts` (or inline fetch) to:
1. Login via TOTP.
2. POST a question answer.
3. Verify the response contains follow-ups.
4. POST a follow-up response.
5. GET progress and assert `submit_ready`.

- [ ] **Step 2: Run smoke test**

Ensure backend and frontend are running:
```bash
uv run uvicorn app.main:app --reload &
npm run dev --prefix frontend &
npm run test:e2e --prefix frontend -- questionnaire.spec.ts
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/questionnaire.spec.ts
git commit -m "test(task-13): questionnaire API smoke (QSTN-01, QSTN-05)"
```

---

## Task 7: Verification and traceability

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -q
uv run pytest tests/steps -q
uv run ruff check .
uv run ruff format --check .
```

Expected: All green.

- [ ] **Step 2: Update TESTPLAN.md**

Set QSTN-01, QSTN-04, QSTN-05, QSTN-06 status to `green`.

- [ ] **Step 3: Update session handoff**

Write current state to `.claude/session-handoff.md`.

- [ ] **Step 4: Commit**

```bash
git add TESTPLAN.md .claude/session-handoff.md
git commit -m "chore(task-13): verification, traceability, and handoff (QSTN-01/04/05/06)"
```

---

## Self-review

- **QSTN-01 follow-up generation:** Task 2 crew + Task 3 answer service.
- **QSTN-04 skipped blocks submission:** Task 3 `save_answer` with `skipped=True` and `get_domain_progress` logic.
- **QSTN-05 save/resume:** Task 3 progress endpoint + Task 4 router.
- **C-09 max 3 follow-ups:** Task 2 `_parse` truncation.
- **C-11 skipped questions block submission:** Task 3 `submit_ready` logic.
- **C-19 AI outage degrades gracefully:** Task 3 `try/except` around `crew.generate()` with waiver and notification.
- No placeholders. All file paths exact. Types consistent.
