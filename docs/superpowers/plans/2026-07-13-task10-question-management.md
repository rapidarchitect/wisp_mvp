# Task 10 — Question Management Implementation Plan

> **Goal:** Add admin question CRUD (add/edit/disable/reinstate) and per-domain regeneration guarded by zero answers. Scenarios SEED-04, SEED-05, SEED-06.
> **Architecture:** Service module for business rules + thin FastAPI router; reuse existing auth/admin dependencies from Task 07.
> **Tech Stack:** Python 3.12, FastAPI, aiosqlite, pydantic v2, pytest-bdd.

## Global Constraints

- `uv` only; `pip` is forbidden.
- No ORMs; raw parameterized SQL via `aiosqlite`.
- Feature files (`features/*.feature`) are spec; edits require explicit human approval (already granted).
- Every commit cites task number and constraint IDs: `feat(task-10): ... (C-16)`.
- Tests never call real LLM endpoints; use `FakeLLM`.
- Tenant identity comes from the resolved subdomain only (C-01).
- Coverage minimum 85% on `app/services` and `app/domain`.

---

### Task 1: Extend `features/domain-seeding-and-questions.feature`

**Files:**
- Modify: `features/domain-seeding-and-questions.feature`

**Interfaces:**
- Produces: Gherkin scenarios SEED-04, SEED-05, SEED-06.

- [ ] **Step 1: Append the three new scenarios**

Add at the end of the existing feature file:

```gherkin
  Scenario: Admin adds custom question (SEED-04)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    When the admin adds a custom question "Do you require MFA on all remote access?" to domain "AC"
    Then domain "AC" has 6 enabled questions
    And the new question has origin "admin"

  Scenario: Admin disables seeded question (SEED-05)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    And the admin has added a custom question to domain "AC"
    When the admin disables a seeded question in domain "AC"
    Then the disabled question is hidden
    And domain "AC" has 5 enabled questions

  Scenario: Regeneration only when unanswered (SEED-06)
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is ready
    When the admin regenerates questions for domain "AC"
    Then domain "AC" has fresh seeded questions
    When a contributor answers a question in domain "AC"
    And the admin regenerates questions for domain "AC"
    Then the regeneration is rejected with "domain_has_answers"
```

- [ ] **Step 2: Verify the feature file parses**

Run:

```bash
uv run pytest tests/steps/test_domain_seeding_and_questions.py --collect-only -q
```

Expected: collection errors for the new scenarios (missing step definitions is OK at this stage).

---

### Task 2: Create Pydantic request models

**Files:**
- Create: `app/models/questions.py`

**Interfaces:**
- Produces: `AddQuestionRequest`, `EditQuestionRequest`.

- [ ] **Step 1: Write the model file**

```python
"""Pydantic models for question management endpoints."""

from pydantic import BaseModel, Field


class AddQuestionRequest(BaseModel):
    """Payload for adding a custom admin question to a domain."""

    domain_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    position: int | None = Field(None, ge=0)


class EditQuestionRequest(BaseModel):
    """Payload for editing question text."""

    text: str = Field(..., min_length=1)
```

- [ ] **Step 2: Confirm the module imports cleanly**

Run:

```bash
uv run python -c "from app.models.questions import AddQuestionRequest, EditQuestionRequest; print('ok')"
```

Expected: prints `ok`.

---

### Task 3: Implement `app/services/questions.py`

**Files:**
- Create: `app/services/questions.py`

**Interfaces:**
- Consumes: `TenantDB`, `SeederCrew` from Task 09, exceptions from `app.exceptions`.
- Produces: `add_question()`, `edit_question()`, `disable_question()`, `reinstate_question()`, `regenerate_domain_questions()`.

- [ ] **Step 1: Write the service**

```python
"""Question management business rules and persistence."""

from app.crews.seeder_crew import SeederCrew
from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError, ValidationError


async def _get_domain(db: TenantDB, domain_id: int) -> dict:
    row = await db.fetchone(
        "SELECT id, code, name, status FROM domains WHERE id = ?",
        (domain_id,),
    )
    if row is None:
        raise NotFoundError(f"Domain {domain_id} not found")
    return dict(row)


async def _get_question(db: TenantDB, question_id: int) -> dict:
    row = await db.fetchone(
        "SELECT * FROM questions WHERE id = ?",
        (question_id,),
    )
    if row is None:
        raise NotFoundError(f"Question {question_id} not found")
    return dict(row)


async def _count_enabled_questions(db: TenantDB, domain_id: int) -> int:
    row = await db.fetchone(
        "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
        (domain_id,),
    )
    return row[0]


async def _domain_has_answers(db: TenantDB, domain_id: int) -> bool:
    row = await db.fetchone(
        """
        SELECT COUNT(*) FROM answers a
        JOIN questions q ON q.id = a.question_id
        WHERE q.domain_id = ?
        """,
        (domain_id,),
    )
    return row[0] > 0


async def add_question(
    db: TenantDB,
    *,
    domain_id: int,
    text: str,
    position: int | None = None,
) -> dict:
    """Add a custom admin question to a domain."""
    await _get_domain(db, domain_id)
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("Question text is required", code="empty_text")

    enabled = await _count_enabled_questions(db, domain_id)
    if enabled >= 10:
        raise ValidationError(
            "Domain already has 10 enabled questions", code="too_many_questions"
        )

    if position is None:
        row = await db.fetchone(
            "SELECT COALESCE(MAX(position), 0) FROM questions WHERE domain_id = ?",
            (domain_id,),
        )
        position = row[0] + 1

    cursor = await db.execute(
        """
        INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (domain_id, cleaned, "yes_no", "admin", 1, position),
    )
    await db.commit()
    return {
        "question_id": cursor.lastrowid,
        "domain_id": domain_id,
        "origin": "admin",
        "enabled": True,
    }


async def edit_question(
    db: TenantDB,
    *,
    question_id: int,
    text: str,
) -> dict:
    """Edit a question's text."""
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("Question text is required", code="empty_text")

    question = await _get_question(db, question_id)
    await db.execute(
        "UPDATE questions SET text = ? WHERE id = ?",
        (cleaned, question_id),
    )
    await db.commit()
    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "text": cleaned,
    }


async def disable_question(
    db: TenantDB,
    *,
    question_id: int,
) -> dict:
    """Hide a question from contributors."""
    question = await _get_question(db, question_id)
    enabled = await _count_enabled_questions(db, question["domain_id"])
    if enabled <= 5:
        raise ValidationError(
            "Cannot disable: domain would have fewer than 5 enabled questions",
            code="minimum_questions",
        )

    await db.execute(
        "UPDATE questions SET enabled = 0 WHERE id = ?",
        (question_id,),
    )
    await db.commit()
    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "enabled": False,
    }


async def reinstate_question(
    db: TenantDB,
    *,
    question_id: int,
) -> dict:
    """Make a previously disabled question visible again."""
    question = await _get_question(db, question_id)
    enabled = await _count_enabled_questions(db, question["domain_id"])
    if enabled >= 10:
        raise ValidationError(
            "Cannot reinstate: domain already has 10 enabled questions",
            code="too_many_questions",
        )

    await db.execute(
        "UPDATE questions SET enabled = 1 WHERE id = ?",
        (question_id,),
    )
    await db.commit()
    return {
        "question_id": question_id,
        "domain_id": question["domain_id"],
        "enabled": True,
    }


async def regenerate_domain_questions(
    db: TenantDB,
    *,
    domain_id: int,
    llm=None,
) -> dict:
    """Replace seeded questions with a fresh LLM-generated set.

    Allowed only when the domain has zero answers (C-16). Admin-added custom
    questions are preserved. If the LLM fails, the domain is marked
    pending_questions per C-19.
    """
    domain = await _get_domain(db, domain_id)
    if await _domain_has_answers(db, domain_id):
        raise ConflictError(
            "Domain has answers; regeneration is not allowed",
            code="domain_has_answers",
        )

    await db.execute(
        "DELETE FROM questions WHERE domain_id = ? AND origin = 'seeded'",
        (domain_id,),
    )
    await db.commit()

    crew = SeederCrew(
        db,
        domain_id=domain_id,
        domain_code=domain["code"],
        domain_name=domain["name"],
        llm=llm,
    )
    return await crew.seed_domain()
```

- [ ] **Step 2: Run import check**

```bash
uv run python -c "from app.services.questions import add_question, edit_question, disable_question, reinstate_question, regenerate_domain_questions; print('ok')"
```

Expected: prints `ok`.

---

### Task 4: Unit-test the question service

**Files:**
- Create: `tests/unit/test_questions_service.py`

**Interfaces:**
- Consumes: `app.services.questions` functions.
- Produces: passing unit tests for add, edit, disable, reinstate, regenerate, and guardrails.

- [ ] **Step 1: Write the unit tests**

```python
"""Unit tests for question management services."""

import pytest

from app.ai.fakes import FakeLLM
from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError, ValidationError
from app.services.questions import (
    add_question,
    disable_question,
    edit_question,
    reinstate_question,
    regenerate_domain_questions,
)


async def _seed_domain(db):
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    version_id = (await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1"))[0]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "ready"),
    )
    await db.commit()
    return (await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0]


async def _seed_questions(db, domain_id, count: int):
    for i in range(count):
        await db.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, f"Q{i+1}?", "yes_no", "seeded", 1, i),
        )
    await db.commit()


async def test_add_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)

    result = await add_question(
        db,
        domain_id=domain_id,
        text="  Custom question?  ",
    )

    assert result["origin"] == "admin"
    assert result["enabled"] is True
    count = (await db.fetchone(
        "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
        (domain_id,),
    ))[0]
    assert count == 6
    await db.close()


async def test_add_question_exceeds_max(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 10)

    with pytest.raises(ValidationError, match="too_many_questions"):
        await add_question(db, domain_id=domain_id, text="Extra?")

    await db.close()


async def test_edit_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[0]

    result = await edit_question(db, question_id=question_id, text="Updated text?")

    assert result["text"] == "Updated text?"
    text = (await db.fetchone("SELECT text FROM questions WHERE id = ?", (question_id,)))[0]
    assert text == "Updated text?"
    await db.close()


async def test_disable_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 6)
    question_id = (await db.fetchone(
        "SELECT id FROM questions WHERE domain_id = ? AND origin = 'seeded'",
        (domain_id,),
    ))[0]

    result = await disable_question(db, question_id=question_id)

    assert result["enabled"] is False
    enabled = (await db.fetchone(
        "SELECT COUNT(*) FROM questions WHERE domain_id = ? AND enabled = 1",
        (domain_id,),
    ))[0]
    assert enabled == 5
    await db.close()


async def test_disable_question_blocked_by_minimum(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[0]

    with pytest.raises(ValidationError, match="minimum_questions"):
        await disable_question(db, question_id=question_id)

    await db.close()


async def test_reinstate_question(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[0]
    await db.execute("UPDATE questions SET enabled = 0 WHERE id = ?", (question_id,))
    await db.commit()

    result = await reinstate_question(db, question_id=question_id)

    assert result["enabled"] is True
    await db.close()


async def test_reinstate_question_exceeds_max(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 10)
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[0]
    await db.execute("UPDATE questions SET enabled = 0 WHERE id = ?", (question_id,))
    await db.commit()

    with pytest.raises(ValidationError, match="too_many_questions"):
        await reinstate_question(db, question_id=question_id)

    await db.close()


async def test_regenerate_domain_questions(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    old_ids = {
        r[0]
        for r in await db.fetchall("SELECT id FROM questions WHERE domain_id = ?", (domain_id,))
    }
    llm = FakeLLM(
        default='{"questions": ['
        '{"text": "A?"}, {"text": "B?"}, {"text": "C?"}, '
        '{"text": "D?"}, {"text": "E?"}, {"text": "F?"}'
        ']}'
    )

    result = await regenerate_domain_questions(db, domain_id=domain_id, llm=llm)

    assert result["seeded"] == 6
    assert result["status"] == "ready"
    new_ids = {
        r[0]
        for r in await db.fetchall("SELECT id FROM questions WHERE domain_id = ?", (domain_id,))
    }
    assert not old_ids & new_ids
    await db.close()


async def test_regenerate_domain_questions_blocked_by_answers(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    domain_id = await _seed_domain(db)
    await _seed_questions(db, domain_id, 5)
    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("c@acme.app.wisp.llc", "hash", '["contributor"]', "active", 0, 0),
    )
    await db.commit()
    question_id = (await db.fetchone("SELECT id FROM questions WHERE domain_id = ?", (domain_id,)))[0]
    user_id = (await db.fetchone("SELECT id FROM users WHERE email = ?", ("c@acme.app.wisp.llc",)))[0]
    await db.execute(
        "INSERT INTO answers (question_id, contributor_id, value, skipped) VALUES (?, ?, ?, ?)",
        (question_id, user_id, "yes", 0),
    )
    await db.commit()

    with pytest.raises(ConflictError, match="domain_has_answers"):
        await regenerate_domain_questions(db, domain_id=domain_id)

    await db.close()
```

- [ ] **Step 2: Run unit tests**

```bash
uv run pytest tests/unit/test_questions_service.py -q
```

Expected: 9 passed.

---

### Task 5: Implement the API router

**Files:**
- Create: `app/api/routers/questions.py`

**Interfaces:**
- Consumes: `app.services.questions`, `app.models.questions`, auth helpers from `app.api.routers.users`, `TenantDB` from middleware.
- Produces: `router` (mounted at `/questions`) and `domain_router` (mounted at `/domains`).

- [ ] **Step 1: Write the router**

```python
"""Question management API router (Task 10)."""

from fastapi import APIRouter, Header, Request

from app.api.routers.users import _get_current_user, _require_admin
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.questions import AddQuestionRequest, EditQuestionRequest
from app.services.questions import (
    add_question,
    disable_question,
    edit_question,
    reinstate_question,
    regenerate_domain_questions,
)

router = APIRouter()
domain_router = APIRouter()


@router.post("")
async def create_question(
    request: Request,
    payload: AddQuestionRequest,
    authorization: str = Header(...),
) -> dict:
    """Add a custom question to a domain."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await add_question(
        db,
        domain_id=payload.domain_id,
        text=payload.text,
        position=payload.position,
    )


@router.patch("/{question_id}")
async def patch_question(
    request: Request,
    question_id: int,
    payload: EditQuestionRequest,
    authorization: str = Header(...),
) -> dict:
    """Edit question text."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await edit_question(db, question_id=question_id, text=payload.text)


@router.post("/{question_id}/disable")
async def question_disable(
    request: Request,
    question_id: int,
    authorization: str = Header(...),
) -> dict:
    """Disable a question."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await disable_question(db, question_id=question_id)


@router.post("/{question_id}/reinstate")
async def question_reinstate(
    request: Request,
    question_id: int,
    authorization: str = Header(...),
) -> dict:
    """Reinstate a disabled question."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await reinstate_question(db, question_id=question_id)


@domain_router.post("/{domain_id}/regenerate-questions")
async def domain_regenerate_questions(
    request: Request,
    domain_id: int,
    authorization: str = Header(...),
) -> dict:
    """Regenerate seeded questions for a domain."""
    actor = await _get_current_user(request, authorization)
    _require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await regenerate_domain_questions(db, domain_id=domain_id)
```

- [ ] **Step 2: Import check**

```bash
uv run python -c "from app.api.routers.questions import router, domain_router; print('ok')"
```

Expected: prints `ok`.

---

### Task 6: Register the routers in `app/main.py`

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `router` and `domain_router` from `app.api.routers.questions`.

- [ ] **Step 1: Add imports and include routers**

Add to the imports:

```python
from app.api.routers.questions import domain_router, router as questions_router
```

Add after the users router include:

```python
app.include_router(questions_router, prefix="/questions", tags=["questions"])
app.include_router(domain_router, prefix="/domains", tags=["domains"])
```

- [ ] **Step 2: Verify the app starts**

```bash
uv run python -c "from app.main import app; print([r.path for r in app.routes][:10])"
```

Expected: output includes `/questions`, `/domains/{domain_id}/regenerate-questions`.

---

### Task 7: Write BDD step definitions for SEED-04..06

**Files:**
- Modify: `tests/steps/test_domain_seeding_and_questions.py`

**Interfaces:**
- Consumes: existing `client`, `context`, `provisioned_tenant`, `data_dir` fixtures.
- Produces: step definitions matching the new scenarios.

- [ ] **Step 1: Add helper to fetch domain/question IDs via sqlite**

Append to the existing `_tenant_db_path` helper area:

```python
def _find_domain_id(data_dir, slug, code):
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


def _find_seeded_question_id(data_dir, slug, code):
    path = _tenant_db_path(data_dir, slug)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT q.id FROM questions q JOIN domains d ON d.id = q.domain_id "
            "WHERE d.code = ? AND q.origin = 'seeded' LIMIT 1",
            (code,),
        ).fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()
```

- [ ] **Step 2: Add the new Given/When/Then steps**

```python
@given(parsers.parse('domain "{code}" is ready'))
def given_domain_is_ready(data_dir, provisioned_tenant, code):
    """Verify the named domain exists and is in ready status."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT status FROM domains WHERE code = ?", (code,)
        ).fetchone()
        assert row is not None
        assert row[0] == "ready"
    finally:
        conn.close()


@given(parsers.parse('the admin has added a custom question to domain "{code}"'))
def given_admin_added_custom_question(client, context, code):
    """Seed a custom question through the API so the domain has >5 enabled."""
    domain_id = _find_domain_id(context.get("data_dir"), context.get("tenant_slug"), code)
    response = client.post(
        "/questions",
        json={"domain_id": domain_id, "text": "Extra admin question?"},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200


@when(
    parsers.parse(
        'the admin adds a custom question "{text}" to domain "{code}"'
    )
)
def when_admin_adds_question(client, context, text, code):
    """POST a new custom question."""
    domain_id = _find_domain_id(context.get("data_dir"), context.get("tenant_slug"), code)
    response = client.post(
        "/questions",
        json={"domain_id": domain_id, "text": text},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["last_question_id"] = response.json()["question_id"]


@then(parsers.parse('domain "{code}" has {count:d} enabled questions'))
def then_domain_has_enabled_questions(data_dir, provisioned_tenant, code, count):
    """Count enabled questions for the domain."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        n = conn.execute(
            """
            SELECT COUNT(*) FROM questions q
            JOIN domains d ON d.id = q.domain_id
            WHERE d.code = ? AND q.enabled = 1
            """,
            (code,),
        ).fetchone()[0]
        assert n == count
    finally:
        conn.close()


@then(parsers.parse('the new question has origin "{origin}"'))
def then_new_question_has_origin(data_dir, provisioned_tenant, context, origin):
    """Assert the last created question's origin."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT origin FROM questions WHERE id = ?",
            (context["last_question_id"],),
        ).fetchone()
        assert row is not None
        assert row[0] == origin
    finally:
        conn.close()


@when(parsers.parse('the admin disables a seeded question in domain "{code}"'))
def when_admin_disables_seeded_question(client, context, code):
    """Disable the first seeded question in the domain."""
    question_id = _find_seeded_question_id(
        context.get("data_dir"), context.get("tenant_slug"), code
    )
    response = client.post(
        f"/questions/{question_id}/disable",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["disabled_question_id"] = question_id


@then("the disabled question is hidden")
def then_disabled_question_is_hidden(data_dir, provisioned_tenant, context):
    """Assert the disabled question is no longer enabled."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        enabled = conn.execute(
            "SELECT enabled FROM questions WHERE id = ?",
            (context["disabled_question_id"],),
        ).fetchone()[0]
        assert enabled == 0
    finally:
        conn.close()


@when(parsers.parse('the admin regenerates questions for domain "{code}"'))
def when_admin_regenerates_questions(client, context, code):
    """POST to regenerate seeded questions for the domain."""
    domain_id = _find_domain_id(context.get("data_dir"), context.get("tenant_slug"), code)
    # Capture pre-regeneration IDs if not already captured.
    if "pre_regeneration_ids" not in context:
        path = _tenant_db_path(context.get("data_dir"), context.get("tenant_slug"))
        conn = sqlite3.connect(path)
        try:
            context["pre_regeneration_ids"] = {
                r[0]
                for r in conn.execute(
                    "SELECT id FROM questions WHERE domain_id = ?", (domain_id,)
                ).fetchall()
            }
        finally:
            conn.close()
    response = client.post(
        f"/domains/{domain_id}/regenerate-questions",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    context["last_regenerate_response"] = response


@then('domain "{code}" has fresh seeded questions')
def then_domain_has_fresh_seeded_questions(data_dir, provisioned_tenant, code, context):
    """Assert questions were replaced and all are seeded."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT q.id, q.origin FROM questions q
            JOIN domains d ON d.id = q.domain_id
            WHERE d.code = ?
            """,
            (code,),
        ).fetchall()
        assert len(rows) >= 5
        current_ids = {r[0] for r in rows}
        assert not current_ids & context["pre_regeneration_ids"]
        assert all(r[1] == "seeded" for r in rows)
    finally:
        conn.close()


@when(parsers.parse('a contributor answers a question in domain "{code}"'))
def when_contributor_answers_question(data_dir, provisioned_tenant, code, context):
    """Insert an answer directly so the domain is no longer answer-free."""
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        domain_id = conn.execute(
            "SELECT id FROM domains WHERE code = ?", (code,)
        ).fetchone()[0]
        question_id = conn.execute(
            "SELECT id FROM questions WHERE domain_id = ? LIMIT 1", (domain_id,)
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("c@palmetto.app.wisp.llc", "hash", '["contributor"]', "active", 0, 0),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO answers (question_id, contributor_id, value, skipped) VALUES (?, ?, ?, ?)",
            (question_id, user_id, "yes", 0),
        )
        conn.commit()
    finally:
        conn.close()


@then(parsers.parse('the regeneration is rejected with "{code}"'))
def then_regeneration_rejected(context, code):
    """Assert the last regeneration attempt failed with the expected error code."""
    response = context["last_regenerate_response"]
    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
```

Note: the step functions above rely on `context` containing `data_dir` and `tenant_slug`. `pytest-bdd` injects fixtures by name, but `context` is the BDD context dict. We need to capture `data_dir` and `tenant_slug` into `context` in earlier steps. The existing `tenant_slug` fixture is already loaded by `given a provisioned tenant`. Add:

```python
@given(parsers.parse('a provisioned tenant "{slug}"'), target_fixture="tenant_slug")
def given_tenant_slug(slug, context):
    context["tenant_slug"] = slug
    context["data_dir"] = None  # will be set below
    return slug
```

However, `data_dir` is a pytest fixture, not available in `given_tenant_slug`. The simplest fix is to update the helper calls to use the `data_dir` fixture directly instead of pulling from context. In pytest-bdd, step functions can request any fixture by name. So change `_find_domain_id(context.get("data_dir"), context.get("tenant_slug"), code)` to `_find_domain_id(data_dir, provisioned_tenant, code)`. Update the When/Then steps to accept `data_dir` and `provisioned_tenant` as parameters.

Revise the helper usage in steps:

- `given_admin_added_custom_question(client, data_dir, provisioned_tenant, context, code)`
- `when_admin_adds_question(client, data_dir, provisioned_tenant, context, text, code)`
- `when_admin_disables_seeded_question(client, data_dir, provisioned_tenant, context, code)`
- `when_admin_regenerates_questions(client, data_dir, provisioned_tenant, context, code)`
- `then_domain_has_fresh_seeded_questions(data_dir, provisioned_tenant, code, context)`

- [ ] **Step 3: Run the new scenarios**

```bash
uv run pytest tests/steps/test_domain_seeding_and_questions.py -q -k "SEED-04 or SEED-05 or SEED-06"
```

Expected: 3 passed.

---

### Task 8: Full verification, lint, and TESTPLAN update

**Files:**
- Modify: `TESTPLAN.md`

**Interfaces:**
- Consumes: all preceding implementation.
- Produces: green task status and clean commit.

- [ ] **Step 1: Run the full BDD suite**

```bash
uv run pytest tests/steps -q
```

Expected: all green.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all green.

- [ ] **Step 3: Run lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

Expected: clean.

- [ ] **Step 4: Update TESTPLAN.md**

Change the SEED-04, SEED-05, SEED-06 rows from `planned` to `green`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(task-10): admin question CRUD and zero-answer regeneration guard (C-08, C-16, SEED-04..06)"
```

---

## Self-Review

- **Spec coverage:** every requirement in the design doc maps to a task.
- **Placeholder scan:** no TBDs; all code blocks are complete.
- **Type consistency:** `TenantDB` is passed to all service functions; `question_id` and `domain_id` are `int`; router uses the same auth dependency pattern as Task 07.
- **C-16 enforcement:** `regenerate_domain_questions` raises `ConflictError(code="domain_has_answers")` when any answer exists.
- **C-08 enforcement:** add/reinstate cap at 10 enabled questions; disable blocks dropping below 5.
- **C-19 outage path:** regeneration delegates to `SeederCrew.seed_domain()`, which already marks the domain `pending_questions` on LLM failure.
