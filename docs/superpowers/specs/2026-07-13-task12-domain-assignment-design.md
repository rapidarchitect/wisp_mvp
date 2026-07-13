# Task 12 — Domain Assignment Design

**Date:** 2026-07-13  
**Task:** 12  
**Scenarios:** ASSN-01, ASSN-02, ASSN-03, ASSN-04, ASSN-05  
**Constraints:** C-10 (exactly one Contributor and one Reviewer per domain; reassignment preserves answers)

## Decisions

- The API operates on the tenant's single in-progress WISP version automatically. No `version_id` is required in URLs today.
- The assigned contributor must hold the `contributor` role and the assigned reviewer must hold the `reviewer` role. Inactive users cannot be assigned.
- Reassignment is allowed only when the domain status is `pending_questions`, `ready`, or `assigned`. It is blocked for `in_progress`, `in_review`, and `approved`.
- A domain is flagged as unassigned when it has no `domain_assignments` row or when either `contributor_id` or `reviewer_id` is missing.
- A single `GET /domains/assigned` endpoint returns every domain assigned to the caller, annotated with the caller's role on that domain.

## Data model

No schema changes are required. The existing `domain_assignments` table already stores exactly one contributor and one reviewer per domain.

Two indexes will be added to `app/db/schema/tenant.sql` for listing queries:

```sql
CREATE INDEX IF NOT EXISTS idx_domain_assignments_contributor ON domain_assignments(contributor_id);
CREATE INDEX IF NOT EXISTS idx_domain_assignments_reviewer ON domain_assignments(reviewer_id);
```

## Service API (`app/services/domain_assignment.py`)

### `assign_domain(db, *, actor_user_id, code, contributor_email, reviewer_email) -> dict`

1. Resolve the current in-progress `wisp_versions` row (`status = 'in_progress'`).
2. Look up the domain by `code` and version id; raise `NotFoundError` if missing.
3. Reject if the domain status is `in_progress`, `in_review`, or `approved`.
4. Look up the contributor and reviewer by email; both must exist, be `active`, and hold the matching role.
5. Read the existing `domain_assignments` row for the domain, if any.
6. Within an immediate transaction:
   - Delete the existing assignment row.
   - Insert a new row with the new `contributor_id` and `reviewer_id`.
   - Update the domain status to `assigned` if it is not already.
   - Write an audit event of type `domain_assigned` with domain code and both user emails.
   - Commit.
7. After the transaction commits, send notifications:
   - Send `domain_unassigned` notification to any displaced contributor or reviewer.
   - Send `domain_assigned` notification to the new contributor and reviewer.
7. Return the assignment record: `{domain_id, code, contributor_id, contributor_email, reviewer_id, reviewer_email, assigned_at}`.

### `get_unassigned_domains(db) -> list[dict]`

Returns all domains in the current in-progress version that are not fully assigned. The query left-joins `domain_assignments` and returns rows where the assignment is missing or `contributor_id`/`reviewer_id` is null.

Each result includes `id`, `code`, `name`, `status`, and a `missing_roles` list (`["contributor"]`, `["reviewer"]`, or `["contributor", "reviewer"]`).

### `list_user_assignments(db, *, user_id) -> list[dict]`

Returns every domain assigned to the user in the current in-progress version, with a `role` field set to `"contributor"` or `"reviewer"`. A user can appear in both roles for different domains.

## HTTP routes (`app/api/routers/domain_assignment.py`)

Mounted under the tenant router at `/domains`.

- `POST /domains/{code}/assign` — admin only.
  - Request body: `{"contributor_email": str, "reviewer_email": str}`
  - Response: assignment record.
- `GET /domains/unassigned` — admin only.
  - Response: list of unassigned domains with `missing_roles`.
- `GET /domains/assigned` — any authenticated user.
  - Response: list of domains assigned to the caller with `role`.

## Notifications and audit

- New assignments trigger `domain_assigned` notifications for both the contributor and reviewer.
- Reassignment triggers `domain_unassigned` notifications for any displaced contributor or reviewer.
- All assignments write an audit event of type `domain_assigned`.

The notification payloads reuse the existing templates:

- `domain_assigned`: subject "You have been assigned to a WISP domain", body includes role and domain name.
- `domain_unassigned`: subject "You have been unassigned from a WISP domain", body includes domain name.

## BDD scenarios (`features/domain-assignment.feature`)

- **ASSN-01** — Admin assigns a contributor and reviewer to a domain.
- **ASSN-02** — Reassigning a domain leaves exactly one contributor and one reviewer.
- **ASSN-03** — Reassignment preserves existing answers and compiled text.
- **ASSN-04** — A contributor's `GET /domains/assigned` shows only their assigned domains.
- **ASSN-05** — Admin `GET /domains/unassigned` flags domains missing either role.

## Testing plan

- Unit tests in `tests/unit/test_services_domain_assignment.py` cover:
  - Successful assignment and status transition.
  - Validation of active users and matching roles.
  - Blocked reassignment for non-eligible statuses.
  - Replacement semantics and displaced-user notifications.
  - Answer and compiled-text preservation on reassignment.
  - `get_unassigned_domains` and `list_user_assignments`.
- BDD step definitions in `tests/steps/test_domain_assignment.py` implement the five scenarios.
- The full BDD suite and lint must remain green.
