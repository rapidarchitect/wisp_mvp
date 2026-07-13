# Task 11 — Notifications Implementation Plan

> **Goal:** Build a single `notify()` service that records in-app notifications and sends transactional emails, expose a current-user feed endpoint, wire it into existing workflows, and keep tests on console backend / mocked SES.
> **Architecture:** Service owns persistence and dispatch; FastAPI router owns the feed; email backend selected by `settings.email_backend`.
> **Tech Stack:** Python 3.12, FastAPI, aiosqlite, pydantic v2, orjson, boto3, pytest-asyncio.

## Global Constraints

- `uv` only; `pip` is forbidden.
- No ORMs; raw parameterized SQL via `aiosqlite`.
- Tests never call real SES endpoints; SES backend is exercised through mocks.
- Tenant identity comes from the resolved subdomain only (C-01).
- Every commit cites task number and constraint IDs.
- Coverage minimum 85% on `app/services` and `app/domain`.

---

### Task 1: Extend email backends with SES and a factory

**Files:**
- Modify: `app/services/email_backends.py`

**Interfaces:**
- Produces: `SESEmailBackend`, `get_email_backend()`.

- [ ] **Step 1: Add SES backend and factory**

```python
import asyncio

import boto3

from app.config import settings


class SESEmailBackend:
    """Send transactional email via AWS SES."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        client = boto3.client("ses", region_name=settings.ses_region)
        await asyncio.to_thread(
            client.send_email,
            Source=settings.email_from,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )


def get_email_backend():
    """Return the configured email backend."""
    if settings.email_backend == "ses":
        return SESEmailBackend()
    return ConsoleEmailBackend()
```

- [ ] **Step 2: Import check**

```bash
uv run python -c "from app.services.email_backends import get_email_backend, SESEmailBackend; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/services/email_backends.py
git commit -m "feat(task-11): SES email backend and backend factory"
```

---

### Task 2: Create notification templates

**Files:**
- Create: `app/services/notification_templates.py`

**Interfaces:**
- Produces: `render(kind, payload) -> (subject, body)`.

- [ ] **Step 1: Write the template registry**

```python
"""Simple string templates for notification emails."""

TEMPLATES: dict[str, tuple[str, str]] = {
    "account_deactivated": (
        "Your WISPGen account has been deactivated",
        "Your WISPGen account ({email}) has been deactivated. Contact your administrator if you believe this was a mistake.",
    ),
    "roles_updated": (
        "Your WISPGen roles have been updated",
        "Your WISPGen roles have been updated to: {roles}.",
    ),
    "domain_assigned": (
        "You have been assigned to a WISP domain",
        "You have been assigned as {role} for the {domain_name} domain.",
    ),
    "domain_unassigned": (
        "You have been unassigned from a WISP domain",
        "You have been removed as {role} for the {domain_name} domain.",
    ),
    "domain_submitted": (
        "A WISP domain is ready for review",
        "The {domain_name} domain has been submitted for review.",
    ),
    "domain_approved": (
        "A WISP domain has been approved",
        "The {domain_name} domain has been approved.",
    ),
    "wisp_complete": (
        "Your WISP is complete",
        "All 14 domains have been approved. Your WISP is complete.",
    ),
}


def render(kind: str, payload: dict) -> tuple[str, str]:
    """Return (subject, body) for a notification kind and payload."""
    if kind not in TEMPLATES:
        raise KeyError(kind)
    subject_template, body_template = TEMPLATES[kind]
    return subject_template.format(**payload), body_template.format(**payload)
```

- [ ] **Step 2: Import check**

```bash
uv run python -c "from app.services.notification_templates import render; print(render('roles_updated', {'roles': 'admin'}))"
```

Expected: prints a tuple.

- [ ] **Step 3: Commit**

```bash
git add app/services/notification_templates.py
git commit -m "feat(task-11): notification templates"
```

---

### Task 3: Implement the notification service

**Files:**
- Create: `app/services/notifications.py`
- Create: `app/models/notification.py`

**Interfaces:**
- Consumes: `TenantDB`, `render`, `get_email_backend`, `orjson`, exceptions.
- Produces: `notify()`, `get_notifications()`, `mark_read()`.

- [ ] **Step 1: Write the Pydantic models**

```python
"""Pydantic models for notification endpoints."""

from pydantic import BaseModel, Field


class NotificationListParams(BaseModel):
    """Query parameters for the notifications feed."""

    unread_only: bool = Field(default=False)
```

- [ ] **Step 2: Write the service**

```python
"""Notification service: in-app feed and transactional email dispatch."""

from datetime import datetime, timezone

import orjson

from app.db.tenant import TenantDB
from app.exceptions import NotFoundError, ValidationError
from app.services.email_backends import get_email_backend
from app.services.notification_templates import render


async def notify(
    db: TenantDB,
    *,
    user_id: int,
    kind: str,
    payload: dict,
    channel: str = "both",
) -> dict:
    """Create a notification and optionally send an email."""
    if channel not in ("in_app", "email", "both"):
        raise ValidationError("channel must be in_app, email, or both", code="invalid_channel")

    try:
        subject, body = render(kind, payload)
    except KeyError as exc:
        raise ValidationError(f"Unknown notification kind: {kind}", code="unknown_kind") from exc

    user = await db.fetchone(
        "SELECT id, email FROM users WHERE id = ?",
        (user_id,),
    )
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    cursor = await db.execute(
        """
        INSERT INTO notifications (user_id, type, payload, channel)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, kind, orjson.dumps(payload).decode("utf-8"), channel),
    )
    notification_id = cursor.lastrowid
    sent_at: str | None = None

    if channel in ("email", "both"):
        backend = get_email_backend()
        await backend.send(to=user["email"], subject=subject, body=body)
        sent_at = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE notifications SET sent_at = ? WHERE id = ?",
            (sent_at, notification_id),
        )

    await db.commit()
    return {
        "notification_id": notification_id,
        "user_id": user_id,
        "kind": kind,
        "channel": channel,
        "sent_at": sent_at,
    }


async def get_notifications(
    db: TenantDB,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Return the user's notification feed, newest first."""
    sql = """
        SELECT id, type, payload, channel, read_at, sent_at
        FROM notifications
        WHERE user_id = ?
    """
    params: list = [user_id]
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = await db.fetchall(sql, tuple(params))
    return [dict(row) for row in rows]


async def mark_read(
    db: TenantDB,
    notification_id: int,
    user_id: int,
) -> dict:
    """Mark a single notification as read."""
    row = await db.fetchone(
        "SELECT user_id FROM notifications WHERE id = ?",
        (notification_id,),
    )
    if row is None or row["user_id"] != user_id:
        raise NotFoundError(f"Notification {notification_id} not found")

    read_at = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE notifications SET read_at = ? WHERE id = ?",
        (read_at, notification_id),
    )
    await db.commit()
    return {"notification_id": notification_id, "read_at": read_at}
```

- [ ] **Step 3: Import check**

```bash
uv run python -c "from app.services.notifications import notify, get_notifications, mark_read; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/services/notifications.py app/models/notification.py
git commit -m "feat(task-11): notification service (C-01)"
```

---

### Task 4: Unit-test the notification service

**Files:**
- Create: `tests/unit/test_services_notifications.py`

**Interfaces:**
- Consumes: `notify()`, `get_notifications()`, `mark_read()`, `SESEmailBackend`.

- [ ] **Step 1: Write tests**

```python
"""Unit tests for the notification service."""

from unittest.mock import MagicMock, patch

import pytest

from app.db.tenant import init_tenant_db
from app.exceptions import NotFoundError, ValidationError
from app.services.email_backends import get_sent_messages
from app.services.notifications import get_notifications, mark_read, notify


async def _seed_user(db, email="admin@acme.app.wisp.llc"):
    await db.execute(
        """
        INSERT INTO users (email, password_hash, roles, status, failed_attempts, totp_enrolled)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, "hash", '["admin"]', "active", 0, 0),
    )
    await db.commit()
    return (await db.fetchone("SELECT id FROM users WHERE email = ?", (email,)))[0]


async def test_notify_creates_in_app_row(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app")

    assert result["notification_id"] is not None
    assert result["channel"] == "in_app"
    assert result["sent_at"] is None
    row = await db.fetchone("SELECT type, channel, sent_at FROM notifications WHERE id = ?", (result["notification_id"],))
    assert row["type"] == "roles_updated"
    assert row["channel"] == "in_app"
    assert row["sent_at"] is None
    await db.close()


async def test_notify_sends_email(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(db, user_id=user_id, kind="account_deactivated", payload={"email": "admin@acme.app.wisp.llc"}, channel="email")

    assert result["sent_at"] is not None
    messages = get_sent_messages()
    assert len(messages) == 1
    assert messages[0]["to"] == "admin@acme.app.wisp.llc"
    await db.close()


async def test_notify_both_channels(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    result = await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "contributor"})

    assert result["channel"] == "both"
    assert result["sent_at"] is not None
    row = await db.fetchone("SELECT channel, sent_at FROM notifications WHERE id = ?", (result["notification_id"],))
    assert row["channel"] == "both"
    assert row["sent_at"] is not None
    await db.close()


async def test_notify_unknown_kind(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)

    with pytest.raises(ValidationError, match="unknown_kind"):
        await notify(db, user_id=user_id, kind="not_a_kind", payload={})

    await db.close()


async def test_notify_user_not_found(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")

    with pytest.raises(NotFoundError):
        await notify(db, user_id=999, kind="roles_updated", payload={"roles": "admin"})

    await db.close()


async def test_get_notifications_orders_by_id(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "a"}, channel="in_app")
    await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "b"}, channel="in_app")

    rows = await get_notifications(db, user_id)

    assert [r["payload"] for r in rows] == [{'roles': 'b'}, {'roles': 'a'}]
    await db.close()


async def test_get_notifications_unread_only(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    r1 = await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "a"}, channel="in_app")
    await mark_read(db, r1["notification_id"], user_id)
    await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "b"}, channel="in_app")

    rows = await get_notifications(db, user_id, unread_only=True)

    assert len(rows) == 1
    assert rows[0]["payload"] == {'roles': 'b'}
    await db.close()


async def test_mark_read(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    result = await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app")

    read = await mark_read(db, result["notification_id"], user_id)

    assert read["read_at"] is not None
    row = await db.fetchone("SELECT read_at FROM notifications WHERE id = ?", (result["notification_id"],))
    assert row["read_at"] is not None
    await db.close()


async def test_mark_read_not_owned(tmp_path):
    db = await init_tenant_db(tmp_path, "acme")
    user_id = await _seed_user(db)
    other_id = await _seed_user(db, email="other@acme.app.wisp.llc")
    result = await notify(db, user_id=user_id, kind="roles_updated", payload={"roles": "admin"}, channel="in_app")

    with pytest.raises(NotFoundError):
        await mark_read(db, result["notification_id"], other_id)

    await db.close()


async def test_ses_backend_send(tmp_path):
    from app.services.email_backends import SESEmailBackend

    backend = SESEmailBackend()
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        await backend.send(to="x@example.com", subject="Hi", body="Hello")

    mock_client.send_email.assert_called_once()
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/unit/test_services_notifications.py -q
```

Expected: 11 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_services_notifications.py
git commit -m "test(task-11): notification service unit tests"
```

---

### Task 5: Implement the notifications API router

**Files:**
- Create: `app/api/routers/notifications.py`

**Interfaces:**
- Consumes: `get_current_user` from `app.api.dependencies`, `TenantDB`, `get_notifications`, `mark_read`.

- [ ] **Step 1: Write the router**

```python
"""Notification feed API router (Task 11)."""

from fastapi import APIRouter, Header, Query, Request

from app.api.dependencies import get_current_user
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.notifications import get_notifications, mark_read

router = APIRouter()


@router.get("")
async def list_notifications(
    request: Request,
    unread_only: bool = Query(default=False),
    authorization: str = Header(...),
) -> list[dict]:
    """Return the current user's notification feed."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await get_notifications(db, user["id"], unread_only=unread_only)


@router.post("/{notification_id}/read")
async def read_notification(
    request: Request,
    notification_id: int,
    authorization: str = Header(...),
) -> dict:
    """Mark a notification as read."""
    user = await get_current_user(request, authorization)
    db = get_tenant_db_from_request(request)
    return await mark_read(db, notification_id, user["id"])
```

- [ ] **Step 2: Import check**

```bash
uv run python -c "from app.api.routers.notifications import router; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/api/routers/notifications.py
git commit -m "feat(task-11): notifications feed API router"
```

---

### Task 6: Register the router

**Files:**
- Modify: `app/main.py`
- Modify: `tests/steps/conftest.py`

**Interfaces:**
- Produces: `/notifications` endpoints in app and test fixtures.

- [ ] **Step 1: Register in `app/main.py`**

Add import:

```python
from app.api.routers.notifications import router as notifications_router
```

Add include:

```python
app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
```

- [ ] **Step 2: Register in `tests/steps/conftest.py` app fixture**

In the `app` fixture, add:

```python
from app.api.routers.notifications import router as notifications_router
application.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
```

- [ ] **Step 3: Run import check**

```bash
uv run python -c "from app.main import app; print([r.path for r in app.routes if 'notification' in r.path])"
```

Expected: output includes `/notifications`.

- [ ] **Step 4: Commit**

```bash
git add app/main.py tests/steps/conftest.py
git commit -m "feat(task-11): register notifications router in app and test fixtures"
```

---

### Task 7: Wire `notify()` into existing workflows

**Files:**
- Modify: `app/services/users.py`
- Modify: `app/services/invitations.py`

**Interfaces:**
- Consumes: `notify()`, `get_email_backend()`.

- [ ] **Step 1: Wire user deactivation and role changes**

In `app/services/users.py`, add import:

```python
from app.services.notifications import notify
```

After setting user status to `inactive` in `deactivate_user`:

```python
await notify(
    db,
    user_id=user_id,
    kind="account_deactivated",
    payload={"email": user["email"]},
    channel="both",
)
```

After updating roles in `set_roles`:

```python
await notify(
    db,
    user_id=target_user_id,
    kind="roles_updated",
    payload={"roles": ", ".join(roles)},
    channel="both",
)
```

- [ ] **Step 2: Send invitation email directly**

In `app/services/invitations.py`, add imports:

```python
from app.config import settings
from app.services.email_backends import get_email_backend
```

After creating the invitation token, send the invitation email:

```python
activation_url = f"https://{db.slug}.{settings.base_domain}/activate?token={token}"
backend = get_email_backend()
await backend.send(
    to=email,
    subject="You have been invited to WISPGen",
    body=f"Click to activate your account: {activation_url}",
)
```

- [ ] **Step 3: Run focused tests**

```bash
uv run pytest tests/unit/test_services_users.py tests/unit/test_services_invitations.py tests/steps/test_user_and_role_management.py -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add app/services/users.py app/services/invitations.py
git commit -m "feat(task-11): wire notify() into user workflows and send invitation emails"
```

---

### Task 8: Full verification and TESTPLAN note

**Files:**
- Modify: `TESTPLAN.md` (Task 11 is scenario-exempt; mark the unit-test verification note)

**Interfaces:**
- Produces: green verification output.

- [ ] **Step 1: Run full suite and lint**

```bash
uv run pytest tests/ -q
uv run ruff check . && uv run ruff format --check .
uv run pytest --cov=app/services --cov-report=term-missing tests/unit/test_services_notifications.py
```

Expected: all green, coverage ≥ 85%.

- [ ] **Step 2: Update TESTPLAN.md**

Add a note in Section 5 or mark Task 11 as scenario-exempt with unit-test verification. No scenario rows change because Task 11 has no BDD scenarios.

- [ ] **Step 3: Commit**

```bash
git add TESTPLAN.md
git commit -m "docs(task-11): TESTPLAN note for scenario-exempt notification service"
```

---

## Self-Review

- **Spec coverage:** every requirement in the design doc maps to a task.
- **Placeholder scan:** no TBDs or incomplete code blocks.
- **Type consistency:** `notify()` signatures match across service, router, and tests.
