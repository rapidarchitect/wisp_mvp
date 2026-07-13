# Task 11 — Notifications Design

> **Approved:** 2026-07-13  
> **Task:** 11  
> **Objective:** Single `notify()` service used by all workflows; in-app feed endpoint; console backend in dev/test, SES in prod.

## Goal

Provide a single notification service that records in-app notifications and sends transactional emails. Wire it into existing user-management workflows so later task scenarios can assert notifications without building new infrastructure.

## Architecture

A service module owns all notification creation, persistence, and dispatch. A thin FastAPI router exposes the current-user feed. Email delivery is abstracted behind a backend interface: console for dev/test, AWS SES for production. The existing `notifications` table in `app/db/schema/tenant.sql` already supports the required shape, so no schema change is needed.

## Data Model

Existing `notifications` table:

| Column | Type | Meaning |
|--------|------|---------|
| `id` | INTEGER PK | notification identifier, also feed order |
| `user_id` | INTEGER FK | recipient |
| `type` | TEXT | notification kind (matches template key) |
| `payload` | TEXT | JSON data for the template |
| `channel` | TEXT | `in_app`, `email`, or `both` |
| `read_at` | TEXT | set when marked read |
| `sent_at` | TEXT | set when email was dispatched |

The feed is ordered by `id DESC`.

## Email Backends

- `ConsoleEmailBackend` — captures messages in memory for tests and prints to stdout for dev.
- `SESEmailBackend` — uses `boto3.client("ses", region_name=settings.ses_region)` and `send_email(Source=settings.email_from, ...)`.
- `get_email_backend()` returns the configured backend based on `settings.email_backend` (`console` or `ses`).

Tests always use the console backend and mock SES when exercising the SES path.

## Notification Templates

A minimal registry in `app/services/notification_templates.py` maps `kind` to `(subject, body_template)`:

- `account_deactivated`
- `roles_updated`
- `domain_assigned`
- `domain_unassigned`
- `domain_submitted`
- `domain_approved`
- `wisp_complete`

Body templates use simple `{placeholder}` substitution from `payload`.

## Service API

```python
async def notify(
    db: TenantDB,
    *,
    user_id: int,
    kind: str,
    payload: dict,
    channel: str = "both",
) -> dict: ...

async def get_notifications(
    db: TenantDB,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]: ...

async def mark_read(
    db: TenantDB,
    notification_id: int,
    user_id: int,
) -> dict: ...
```

`notify` validates the kind, inserts a notification row, looks up the user email, and dispatches email when the channel includes `email`.

## HTTP API

Authenticated endpoints (any signed-in user, not admin-only):

| Method | Path | Action |
|--------|------|--------|
| GET | `/notifications` | `get_notifications` for current user; optional `unread_only` query |
| POST | `/notifications/{notification_id}/read` | `mark_read` for current user |

## Wiring into Existing Workflows

- `app/services/users.py` `deactivate_user`: notify the deactivated user (`account_deactivated`).
- `app/services/users.py` `set_roles`: notify the target user (`roles_updated`).
- `app/services/invitations.py` `invite_user`: the invitee is not yet a user, so the invitation email is sent directly via the configured email backend. After activation, future notifications use `notify`.

## Files to Create

- `app/models/notification.py`
- `app/services/notification_templates.py`
- `app/services/notifications.py`
- `app/api/routers/notifications.py`
- `tests/unit/test_services_notifications.py`

## Files to Modify

- `app/services/email_backends.py` (add SES backend + factory)
- `app/services/users.py` (call notify on deactivate and role change)
- `app/services/invitations.py` (send invitation email directly)
- `app/main.py` (register notifications router)
- `tests/steps/conftest.py` (mount notifications router in test `app` fixture)

## Verification

- `uv run pytest tests/unit/test_services_notifications.py -q` green
- `uv run pytest tests/ -q` green
- `uv run ruff check . && uv run ruff format --check .` clean
- Coverage on `app/services` ≥ 85%
