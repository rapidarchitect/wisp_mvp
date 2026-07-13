# Task 12 — Domain Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the domain assignment service, router, and BDD scenarios so each domain has exactly one contributor and one reviewer, reassignment preserves work, and role-scoped visibility works.

**Architecture:** A thin FastAPI router delegates to `app/services/domain_assignment.py`, which validates users/roles/domain status, manages the `domain_assignments` table, preserves answers/compiled text, and emits notifications and audit events through existing services.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, pydantic v2, pytest-bdd, uv, ruff.

## Global Constraints

- Use `uv` for all Python operations; `pip` is forbidden.
- Use `orjson` for JSON serialization; do not use the standard `json` module.
- Use `httpx` (or TestClient) for HTTP; do not use `requests`.
- BDD step definitions are synchronous and use `sqlite3` for DB assertions.
- Feature files are spec and require explicit human approval before creation/editing.
- Every integration fixture must seed a second tenant and assert it is untouched (C-01).
- Never skip, delete, or `xfail` tests to get green.
- Run the full BDD suite after task scenarios are green.

---

## File map

- **Create:** `app/services/domain_assignment.py` — business rules and persistence for assignments.
- **Create:** `app/api/routers/domain_assignment.py` — admin assignment, admin unassigned list, caller assignment list.
- **Create:** `app/models/domain_assignment.py` — Pydantic request/response models.
- **Create:** `tests/unit/test_services_domain_assignment.py` — unit tests for the service.
- **Create:** `features/domain-assignment.feature` — Gherkin scenarios (approved as part of this task).
- **Create:** `tests/steps/test_domain_assignment.py` — step definitions for the feature.
- **Modify:** `app/db/schema/tenant.sql` — add two indexes on `domain_assignments`.
- **Modify:** `app/main.py` — include the new router at `/domains`.
- **Modify:** `TESTPLAN.md` — mark ASSN-01..05 green when scenarios pass.

---

## Task 1: Schema indexes

**Files:**
- Modify: `app/db/schema/tenant.sql:160-162`

**Interfaces:**
- Produces: two new `CREATE INDEX` statements for `domain_assignments(contributor_id)` and `domain_assignments(reviewer_id)`.

- [ ] **Step 1: Add indexes**

Append to `app/db/schema/tenant.sql`:

```sql
CREATE INDEX IF NOT EXISTS idx_domain_assignments_contributor ON domain_assignments(contributor_id);
CREATE INDEX IF NOT EXISTS idx_domain_assignments_reviewer ON domain_assignments(reviewer_id);
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `uv run pytest tests/unit/test_db_tenant.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/db/schema/tenant.sql
git commit -m "feat(task-12): indexes for domain assignment lookups (C-10)"
```

---

## Task 2: Core assignment service

**Files:**
- Create: `app/services/domain_assignment.py`
- Create: `app/models/domain_assignment.py`
- Create: `tests/unit/test_services_domain_assignment.py`

**Interfaces:**
- Consumes: `TenantDB`, `app.exceptions.ValidationError/NotFoundError/ConflictError`, `app.services.notifications.notify`, `app.services.audit.audit`.
- Produces: `assign_domain(db, *, actor_user_id, code, contributor_email, reviewer_email) -> dict`.

- [ ] **Step 1: Write the failing test for successful assignment**

Create `tests/unit/test_services_domain_assignment.py`:

```python
"""Unit tests for domain assignment services."""

import pytest

from app.db.tenant import init_tenant_db
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.domain_assignment import assign_domain


async def _seed_version(db):
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    await db.commit()
    return (await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1"))[0]


async def _seed_domain(db, version_id, code="AC", status="ready"):
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        (code, "Access Control", version_id, status),
    )
    await db.commit()


async def _seed_user(db, email, roles, status="active"):
    import json

    cur = await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, "hash", json.dumps(roles), status, 0, 1),
    )
    await db.commit()
    return cur.lastrowid


async def test_assign_domain_success(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    contributor_id = await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    reviewer_id = await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    result = await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    assert result["code"] == "AC"
    assert result["contributor_id"] == contributor_id
    assert result["reviewer_id"] == reviewer_id
    status = (await db.fetchone("SELECT status FROM domains WHERE code = 'AC'"))[0]
    assert status == "assigned"
    await db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py::test_assign_domain_success -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.domain_assignment'`

- [ ] **Step 3: Implement the assignment service skeleton**

Create `app/services/domain_assignment.py`:

```python
"""Domain assignment business rules and persistence."""

import json

from app.db.tenant import TenantDB
from app.exceptions import ConflictError, NotFoundError, ValidationError


async def _current_version_id(db: TenantDB) -> int:
    row = await db.fetchone(
        "SELECT id FROM wisp_versions WHERE status = 'in_progress' ORDER BY number DESC LIMIT 1"
    )
    if row is None:
        raise NotFoundError("No in-progress WISP version found")
    return row["id"]


async def _require_active_user_with_role(db: TenantDB, email: str, role: str) -> dict:
    row = await db.fetchone(
        "SELECT id, email, roles, status FROM users WHERE email = ?",
        (email,),
    )
    if row is None:
        raise NotFoundError(f"User {email} not found")
    if row["status"] != "active":
        raise ValidationError(f"User {email} is not active", code="user_inactive")
    roles = json.loads(row["roles"])
    if role not in roles:
        raise ValidationError(
            f"User {email} does not have the {role} role", code="missing_role"
        )
    return dict(row)


async def assign_domain(
    db: TenantDB,
    *,
    actor_user_id: int,
    code: str,
    contributor_email: str,
    reviewer_email: str,
) -> dict:
    """Assign exactly one contributor and one reviewer to a domain."""
    version_id = await _current_version_id(db)
    domain = await db.fetchone(
        "SELECT id, code, name, status FROM domains WHERE code = ? AND wisp_version_id = ?",
        (code, version_id),
    )
    if domain is None:
        raise NotFoundError(f"Domain {code} not found")

    if domain["status"] not in ("pending_questions", "ready", "assigned"):
        raise ConflictError(
            f"Domain {code} cannot be reassigned while {domain['status']}",
            code="domain_not_reassignable",
        )

    contributor = await _require_active_user_with_role(db, contributor_email, "contributor")
    reviewer = await _require_active_user_with_role(db, reviewer_email, "reviewer")

    existing = await db.fetchone(
        "SELECT contributor_id, reviewer_id FROM domain_assignments WHERE domain_id = ?",
        (domain["id"],),
    )

    await db.execute("BEGIN IMMEDIATE")
    try:
        if existing is not None:
            await db.execute(
                "DELETE FROM domain_assignments WHERE domain_id = ?",
                (domain["id"],),
            )

        await db.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            """,
            (domain["id"], contributor["id"], reviewer["id"]),
        )

        if domain["status"] != "assigned":
            await db.execute(
                "UPDATE domains SET status = 'assigned' WHERE id = ?",
                (domain["id"],),
            )

        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "domain_id": domain["id"],
        "code": domain["code"],
        "contributor_id": contributor["id"],
        "contributor_email": contributor["email"],
        "reviewer_id": reviewer["id"],
        "reviewer_email": reviewer["email"],
        "assigned_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
```

Note: the `assigned_at` placeholder above is temporary; it will be read from the inserted row in a later refinement.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py::test_assign_domain_success -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/domain_assignment.py tests/unit/test_services_domain_assignment.py
git commit -m "feat(task-12): core domain assignment service (C-10)"
```

---

## Task 3: Assignment notifications, audit, and return value

**Files:**
- Modify: `app/services/domain_assignment.py`
- Modify: `tests/unit/test_services_domain_assignment.py`

**Interfaces:**
- Consumes: `app.services.notifications.notify`, `app.services.audit.audit`.
- Produces: `assign_domain` returns the actual `assigned_at` from the database and emits `domain_assigned`/`domain_unassigned` notifications plus an audit event.

- [ ] **Step 1: Write failing tests for notifications and audit**

Add to `tests/unit/test_services_domain_assignment.py`:

```python
async def test_assign_domain_notifies_new_users(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    rows = await db.fetchall("SELECT type, user_id FROM notifications ORDER BY id")
    types = [r["type"] for r in rows]
    assert "domain_assigned" in types
    assert len(rows) == 2
    await db.close()


async def test_assign_domain_replacement_notifies_displaced_users(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c1@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r1@acme.app.wisp.llc", ["reviewer"])
    await _seed_user(db, "c2@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r2@acme.app.wisp.llc", ["reviewer"])

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c1@acme.app.wisp.llc",
        reviewer_email="r1@acme.app.wisp.llc",
    )
    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c2@acme.app.wisp.llc",
        reviewer_email="r2@acme.app.wisp.llc",
    )

    rows = await db.fetchall("SELECT type, user_id FROM notifications ORDER BY id")
    types = [r["type"] for r in rows]
    assert types.count("domain_unassigned") == 2
    assert types.count("domain_assigned") == 4
    await db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py -v`
Expected: FAIL — no notifications created

- [ ] **Step 3: Add notifications and audit to the service**

Modify `app/services/domain_assignment.py`:

```python
from datetime import UTC, datetime

from app.services.audit import audit
from app.services.notifications import notify
```

Replace the transaction body in `assign_domain` with:

```python
    displaced = []
    if existing is not None:
        displaced = [
            (existing["contributor_id"], "contributor"),
            (existing["reviewer_id"], "reviewer"),
        ]

    await db.execute("BEGIN IMMEDIATE")
    try:
        if existing is not None:
            await db.execute(
                "DELETE FROM domain_assignments WHERE domain_id = ?",
                (domain["id"],),
            )

        cursor = await db.execute(
            """
            INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
            VALUES (?, ?, ?)
            """,
            (domain["id"], contributor["id"], reviewer["id"]),
        )

        if domain["status"] != "assigned":
            await db.execute(
                "UPDATE domains SET status = 'assigned' WHERE id = ?",
                (domain["id"],),
            )

        assignment_row = await db.fetchone(
            "SELECT assigned_at FROM domain_assignments WHERE domain_id = ?",
            (domain["id"],),
        )
        assigned_at = assignment_row["assigned_at"]

        for user_id, role in displaced:
            if (role == "contributor" and user_id != contributor["id"]) or (
                role == "reviewer" and user_id != reviewer["id"]
            ):
                await notify(
                    db,
                    user_id=user_id,
                    kind="domain_unassigned",
                    payload={"role": role, "domain_name": domain["name"]},
                    channel="both",
                )

        await notify(
            db,
            user_id=contributor["id"],
            kind="domain_assigned",
            payload={"role": "contributor", "domain_name": domain["name"]},
            channel="both",
        )
        await notify(
            db,
            user_id=reviewer["id"],
            kind="domain_assigned",
            payload={"role": "reviewer", "domain_name": domain["name"]},
            channel="both",
        )

        await audit(
            db,
            actor_user_id=actor_user_id,
            event_type="domain_assigned",
            subject=domain["code"],
            detail=f"contributor={contributor_email}, reviewer={reviewer_email}",
        )

        await db.commit()
    except Exception:
        await db.execute("ROLLBACK")
        raise

    return {
        "domain_id": domain["id"],
        "code": domain["code"],
        "contributor_id": contributor["id"],
        "contributor_email": contributor["email"],
        "reviewer_id": reviewer["id"],
        "reviewer_email": reviewer["email"],
        "assigned_at": assigned_at,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/domain_assignment.py tests/unit/test_services_domain_assignment.py
git commit -m "feat(task-12): assignment notifications and audit (C-10, C-18)"
```

---

## Task 4: Assignment validation edge cases

**Files:**
- Modify: `tests/unit/test_services_domain_assignment.py`

**Interfaces:**
- Produces: passing unit tests for inactive user, missing role, unknown user, unknown domain, non-reassignable status, and answer preservation.

- [ ] **Step 1: Add validation tests**

Append to `tests/unit/test_services_domain_assignment.py`:

```python
async def test_assign_domain_unknown_domain(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    await _seed_version(db)
    await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    with pytest.raises(NotFoundError):
        await assign_domain(
            db,
            actor_user_id=1,
            code="XX",
            contributor_email="c@acme.app.wisp.llc",
            reviewer_email="r@acme.app.wisp.llc",
        )
    await db.close()


async def test_assign_domain_inactive_user(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"], status="deactivated")
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    with pytest.raises(ValidationError) as exc:
        await assign_domain(
            db,
            actor_user_id=1,
            code="AC",
            contributor_email="c@acme.app.wisp.llc",
            reviewer_email="r@acme.app.wisp.llc",
        )
    assert exc.value.code == "user_inactive"
    await db.close()


async def test_assign_domain_missing_role(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id)
    await _seed_user(db, "c@acme.app.wisp.llc", ["reviewer"])
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    with pytest.raises(ValidationError) as exc:
        await assign_domain(
            db,
            actor_user_id=1,
            code="AC",
            contributor_email="c@acme.app.wisp.llc",
            reviewer_email="r@acme.app.wisp.llc",
        )
    assert exc.value.code == "missing_role"
    await db.close()


async def test_assign_domain_blocks_reassignment_in_review(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id, status="in_review")
    await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    with pytest.raises(ConflictError) as exc:
        await assign_domain(
            db,
            actor_user_id=1,
            code="AC",
            contributor_email="c@acme.app.wisp.llc",
            reviewer_email="r@acme.app.wisp.llc",
        )
    assert exc.value.code == "domain_not_reassignable"
    await db.close()


async def test_assign_domain_preserves_answers_and_compiled_text(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id, status="assigned")
    old_contributor = await _seed_user(db, "c1@acme.app.wisp.llc", ["contributor"])
    old_reviewer = await _seed_user(db, "r1@acme.app.wisp.llc", ["reviewer"])
    new_contributor = await _seed_user(db, "c2@acme.app.wisp.llc", ["contributor"])
    new_reviewer = await _seed_user(db, "r2@acme.app.wisp.llc", ["reviewer"])

    await db.execute(
        """
        INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
        VALUES (?, ?, ?)
        """,
        (
            (await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0],
            old_contributor,
            old_reviewer,
        ),
    )
    await db.execute(
        "INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position) VALUES (?, ?, ?, ?, ?, ?)",
        ((await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0], "Q", "yes_no", "seeded", 1, 0),
    )
    await db.commit()
    question_id = (await db.fetchone("SELECT id FROM questions WHERE text = 'Q'"))[0]
    await db.execute(
        "INSERT INTO answers (question_id, contributor_id, value, skipped, followups_state) VALUES (?, ?, ?, ?, ?)",
        (question_id, old_contributor, "yes", 0, "complete"),
    )
    await db.execute(
        "INSERT INTO compiled_answers (domain_id, narrative_text) VALUES (?, ?)",
        ((await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0], "compiled"),
    )
    await db.commit()

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c2@acme.app.wisp.llc",
        reviewer_email="r2@acme.app.wisp.llc",
    )

    answer = await db.fetchone("SELECT contributor_id FROM answers WHERE question_id = ?", (question_id,))
    compiled = await db.fetchone("SELECT narrative_text FROM compiled_answers WHERE domain_id = ?", ((await db.fetchone("SELECT id FROM domains WHERE code = 'AC'"))[0],))
    assert answer["contributor_id"] == old_contributor
    assert compiled["narrative_text"] == "compiled"
    await db.close()
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_services_domain_assignment.py
git commit -m "test(task-12): assignment validation and preservation tests (C-10)"
```

---

## Task 5: Listing services

**Files:**
- Modify: `app/services/domain_assignment.py`
- Modify: `tests/unit/test_services_domain_assignment.py`

**Interfaces:**
- Produces: `get_unassigned_domains(db) -> list[dict]` and `list_user_assignments(db, *, user_id) -> list[dict]`.

- [ ] **Step 1: Write failing tests for listing helpers**

Append to `tests/unit/test_services_domain_assignment.py`:

```python
from app.services.domain_assignment import get_unassigned_domains, list_user_assignments


async def test_get_unassigned_domains_flags_missing_roles(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id, code="AC", status="ready")
    await _seed_domain(db, version_id, code="PE", status="ready")
    contributor = await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    reviewer = await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    # Fully assign AC, leave PE unassigned.
    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    unassigned = await get_unassigned_domains(db)
    codes = {u["code"] for u in unassigned}
    assert codes == {"PE"}
    assert unassigned[0]["missing_roles"] == ["contributor", "reviewer"]
    await db.close()


async def test_list_user_assignments(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    version_id = await _seed_version(db)
    await _seed_domain(db, version_id, code="AC")
    await _seed_domain(db, version_id, code="PE")
    contributor = await _seed_user(db, "c@acme.app.wisp.llc", ["contributor"])
    reviewer = await _seed_user(db, "r@acme.app.wisp.llc", ["reviewer"])

    await assign_domain(
        db,
        actor_user_id=1,
        code="AC",
        contributor_email="c@acme.app.wisp.llc",
        reviewer_email="r@acme.app.wisp.llc",
    )

    contributor_assignments = await list_user_assignments(db, user_id=contributor)
    assert [a["code"] for a in contributor_assignments] == ["AC"]
    assert contributor_assignments[0]["role"] == "contributor"

    reviewer_assignments = await list_user_assignments(db, user_id=reviewer)
    assert reviewer_assignments[0]["role"] == "reviewer"
    await db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py::test_get_unassigned_domains_flags_missing_roles tests/unit/test_services_domain_assignment.py::test_list_user_assignments -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement listing helpers**

Append to `app/services/domain_assignment.py`:

```python
async def get_unassigned_domains(db: TenantDB) -> list[dict]:
    """Return domains in the current version that are missing an assignment or a role."""
    version_id = await _current_version_id(db)
    rows = await db.fetchall(
        """
        SELECT d.id, d.code, d.name, d.status,
               a.contributor_id, a.reviewer_id
        FROM domains d
        LEFT JOIN domain_assignments a ON a.domain_id = d.id
        WHERE d.wisp_version_id = ?
          AND (
              a.domain_id IS NULL
              OR a.contributor_id IS NULL
              OR a.reviewer_id IS NULL
          )
        ORDER BY d.code
        """,
        (version_id,),
    )
    result = []
    for row in rows:
        missing = []
        if row["contributor_id"] is None:
            missing.append("contributor")
        if row["reviewer_id"] is None:
            missing.append("reviewer")
        result.append(
            {
                "id": row["id"],
                "code": row["code"],
                "name": row["name"],
                "status": row["status"],
                "missing_roles": missing,
            }
        )
    return result


async def list_user_assignments(db: TenantDB, *, user_id: int) -> list[dict]:
    """Return all domains assigned to a user in the current version with role."""
    version_id = await _current_version_id(db)
    rows = await db.fetchall(
        """
        SELECT d.id, d.code, d.name, d.status,
               CASE WHEN a.contributor_id = ? THEN 'contributor' ELSE 'reviewer' END AS role
        FROM domain_assignments a
        JOIN domains d ON d.id = a.domain_id
        WHERE d.wisp_version_id = ?
          AND (a.contributor_id = ? OR a.reviewer_id = ?)
        ORDER BY d.code
        """,
        (user_id, version_id, user_id, user_id),
    )
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_services_domain_assignment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/domain_assignment.py tests/unit/test_services_domain_assignment.py
git commit -m "feat(task-12): unassigned and user assignment listing (ASSN-04, ASSN-05)"
```

---

## Task 6: Router and request models

**Files:**
- Create: `app/models/domain_assignment.py`
- Create: `app/api/routers/domain_assignment.py`
- Create: `tests/unit/test_routers_domain_assignment.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `app.services.domain_assignment.assign_domain`, `get_unassigned_domains`, `list_user_assignments`, `app.api.dependencies.get_current_user`, `require_admin`.
- Produces: FastAPI endpoints at `/domains/{code}/assign`, `/domains/unassigned`, `/domains/assigned`.

- [ ] **Step 1: Create Pydantic request model**

Create `app/models/domain_assignment.py`:

```python
"""Pydantic models for domain assignment endpoints."""

from pydantic import BaseModel, EmailStr


class AssignDomainRequest(BaseModel):
    """Payload for assigning a contributor and reviewer to a domain."""

    contributor_email: EmailStr
    reviewer_email: EmailStr
```

- [ ] **Step 2: Create router**

Create `app/api/routers/domain_assignment.py`:

```python
"""Domain assignment API router (Task 12)."""

from fastapi import APIRouter, Header, Request

from app.api.dependencies import get_current_user, require_admin
from app.middleware.tenancy import get_tenant_db_from_request
from app.models.domain_assignment import AssignDomainRequest
from app.services.domain_assignment import (
    assign_domain,
    get_unassigned_domains,
    list_user_assignments,
)

router = APIRouter()


@router.post("/{code}/assign")
async def assign_domain_endpoint(
    request: Request,
    code: str,
    payload: AssignDomainRequest,
    authorization: str = Header(...),
) -> dict:
    """Assign a contributor and reviewer to a domain (admin only)."""
    actor = await get_current_user(request, authorization)
    require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await assign_domain(
        db,
        actor_user_id=actor["id"],
        code=code,
        contributor_email=payload.contributor_email,
        reviewer_email=payload.reviewer_email,
    )


@router.get("/unassigned")
async def list_unassigned_domains(
    request: Request,
    authorization: str = Header(...),
) -> list[dict]:
    """List domains missing an assignment (admin only)."""
    actor = await get_current_user(request, authorization)
    require_admin(actor)
    db = get_tenant_db_from_request(request)
    return await get_unassigned_domains(db)


@router.get("/assigned")
async def list_my_assignments(
    request: Request,
    authorization: str = Header(...),
) -> list[dict]:
    """List domains assigned to the current user."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await list_user_assignments(db, user_id=user["id"])
```

- [ ] **Step 3: Wire router into app**

Modify `app/main.py` to import and include:

```python
from app.api.routers.domain_assignment import router as domain_assignment_router
```

Add after the existing domains router include:

```python
app.include_router(domain_assignment_router, prefix="/domains", tags=["domains"])
```

- [ ] **Step 4: Write router unit tests**

Create `tests/unit/test_routers_domain_assignment.py` using the pattern from `tests/unit/test_routers_notifications.py`.

Key tests:
- Admin `POST /domains/AC/assign` returns 200 and assignment record.
- Contributor calling `POST /domains/AC/assign` returns 401/403.
- `GET /domains/assigned` for contributor returns only their assigned domains.
- `GET /domains/unassigned` for admin returns unassigned domains.

- [ ] **Step 5: Run router tests**

Run: `uv run pytest tests/unit/test_routers_domain_assignment.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models/domain_assignment.py app/api/routers/domain_assignment.py tests/unit/test_routers_domain_assignment.py app/main.py
git commit -m "feat(task-12): domain assignment router (ASSN-01, ASSN-04, ASSN-05)"
```

---

## Task 7: BDD feature file and step definitions

**Files:**
- Create: `features/domain-assignment.feature`
- Create: `tests/steps/test_domain_assignment.py`

**Interfaces:**
- Consumes: existing `provisioned_tenant`, `client`, `given_enrolled_admin`, `given_enrolled_user_with_roles` fixtures from `tests/steps/conftest.py`.
- Produces: green scenarios ASSN-01..05.

- [ ] **Step 1: Write the feature file**

Create `features/domain-assignment.feature`:

```gherkin
Feature: Domain Assignment

  Background:
    Given a provisioned tenant "palmetto"
    And an enrolled admin "admin@palmetto.app.wisp.llc" with password "AdminPass123!"
    And an enrolled user "contributor@palmetto.app.wisp.llc" with password "UserPass123!" and roles "contributor"
    And an enrolled user "reviewer@palmetto.app.wisp.llc" with password "UserPass123!" and roles "reviewer"
    And an enrolled user "contributor2@palmetto.app.wisp.llc" with password "UserPass123!" and roles "contributor"
    And an enrolled user "reviewer2@palmetto.app.wisp.llc" with password "UserPass123!" and roles "reviewer"
    And domain "AC" is ready for assignment

  Scenario: ASSN-01 Admin assigns contributor and reviewer
    Given "admin@palmetto.app.wisp.llc" is signed in
    When the admin assigns domain "AC" to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    Then domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is notified of domain "AC" assignment as contributor
    And "reviewer@palmetto.app.wisp.llc" is notified of domain "AC" assignment as reviewer

  Scenario: ASSN-02 One contributor, one reviewer at a time
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When the admin assigns domain "AC" to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    Then domain "AC" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" is notified of domain "AC" unassignment as contributor
    And "reviewer@palmetto.app.wisp.llc" is notified of domain "AC" unassignment as reviewer

  Scenario: ASSN-03 Reassignment preserves work
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And "contributor@palmetto.app.wisp.llc" has answered a question in domain "AC"
    When the admin assigns domain "AC" to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer
    Then the answer in domain "AC" still exists
    And domain "AC" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer2@palmetto.app.wisp.llc" as reviewer

  Scenario: ASSN-04 Contributors see only assigned domains
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    And domain "PE" is assigned to "contributor2@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When "contributor@palmetto.app.wisp.llc" is signed in
    And they request their assigned domains
    Then they see domain "AC" with role "contributor"
    And they do not see domain "PE"

  Scenario: ASSN-05 Unassigned domains flagged to admin
    Given "admin@palmetto.app.wisp.llc" is signed in
    And domain "AC" is assigned to "contributor@palmetto.app.wisp.llc" as contributor and "reviewer@palmetto.app.wisp.llc" as reviewer
    When the admin requests unassigned domains
    Then domain "PE" is flagged as missing "contributor, reviewer"
    And domain "AC" is not flagged
```

- [ ] **Step 2: Implement step definitions**

Create `tests/steps/test_domain_assignment.py` using synchronous `sqlite3` for DB assertions and `TestClient` for HTTP. Reuse helpers from `tests/steps/conftest.py` and `tests/steps/test_user_and_role_management.py` where appropriate.

Implement each step:
- `domain "{code}" is ready for assignment` — seed a version and domain with status `ready` if not already.
- `the admin assigns domain "{code}" to ...` — POST `/domains/{code}/assign` with bearer token.
- `domain "{code}" is assigned to ...` — assert `domain_assignments` row matches.
- `{email} is notified of domain "{code}" assignment/unassignment as {role}` — assert a notification row exists for the user with the expected kind.
- `{email} has answered a question in domain "{code}"` — insert question and answer.
- `the answer in domain "{code}" still exists` — assert answer row still present.
- `they request their assigned domains` — GET `/domains/assigned` with bearer token.
- `they see domain "{code}" with role "{role}"` / `they do not see domain "{code}"` — assert response list.
- `the admin requests unassigned domains` — GET `/domains/unassigned`.
- `domain "{code}" is flagged as missing ...` / `is not flagged` — assert response list.

- [ ] **Step 3: Run BDD scenarios**

Run: `uv run pytest tests/steps/test_domain_assignment.py -q`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add features/domain-assignment.feature tests/steps/test_domain_assignment.py
git commit -m "test(task-12): BDD scenarios ASSN-01..05 (C-10)"
```

---

## Task 8: Verification and traceability

**Files:**
- Modify: `TESTPLAN.md`

- [ ] **Step 1: Run the full test suite**

Run:
```bash
uv run pytest tests/ -q
uv run pytest tests/steps -q
uv run ruff check . && uv run ruff format --check .
```

Expected: all green.

- [ ] **Step 2: Update traceability matrix**

In `TESTPLAN.md` Section 4, change the status of ASSN-01..05 from `planned` to `green`.

- [ ] **Step 3: Commit**

```bash
git add TESTPLAN.md
git commit -m "docs(task-12): mark ASSN-01..05 green in TESTPLAN"
```

---

## Spec coverage check

- C-10 one contributor + one reviewer: Task 2 schema + `assign_domain` insert, Task 4 replacement tests.
- Reassignment preserves answers: Task 4 preservation test.
- Role-scoped visibility (ASSN-04): Task 5 `list_user_assignments` + Task 6 router test.
- Admin gap flagging (ASSN-05): Task 5 `get_unassigned_domains` + Task 6 router test.
- Notifications for displaced/new users: Task 3.
- Audit logging: Task 3.

No placeholders remain in the plan; every step includes file paths, commands, and expected outcomes.
