# Task 16 — Versioning and PDF Export Implementation Plan

**Branch:** `task-16-versioning-export`  
**Scenarios:** VERS-01, VERS-02, VERS-03, VERS-04, VERS-05  
**Spec source:** SPEC.md Section 8 (Task 16), constitution C-13, C-14, C-15.

## Objective

Implement WISP version lifecycle and PDF export: render a WeasyPrint PDF from the current version, gate the DRAFT watermark on version status (C-13), clone approved answers into a new version (C-14 single-in-progress guard), keep prior versions immutable and exportable (C-15).

## Scenario definitions

| ID | Scenario | Key assertions |
|---|---|---|
| VERS-01 | Draft export carries DRAFT watermark | Export an `in_progress` version; generated PDF text contains `DRAFT` |
| VERS-02 | Complete WISP exports clean | Approve all domains, export; generated PDF text does NOT contain `DRAFT` |
| VERS-03 | New version clones approved baseline | Start new version; approved domain answers/narratives copied, in_progress domains reset |
| VERS-04 | Only one version in progress | Starting a second version while one is in_progress returns a conflict |
| VERS-05 | Prior versions remain exportable | Complete version 1, start version 2, then export version 1 still succeeds |

## Files to create

- `app/services/pdf.py` — `render_wisp_pdf(db, version_id, *, include_draft: bool)` returning PDF bytes.
- `app/services/versions.py` — `start_new_version(db, tenant_id, previous_version_id)`, `get_version(db, version_id)`, `list_versions(db)`, `version_complete(db, version_id)` helper.
- `app/templates/wisp.html` — Jinja2 HTML template for the PDF: company vitals, logo, 14 domain narratives, DRAFT watermark div when `include_draft` is true.
- `app/api/routers/versions.py` — `GET /versions`, `GET /versions/{id}/export`, `POST /versions`.
- `tests/unit/test_services_pdf.py`, `tests/unit/test_services_versions.py`, `tests/unit/test_routers_versions.py`.
- `tests/steps/test_wisp_versioning_and_export.py` — BDD step definitions.

## Files to modify

- `app/main.py` — register version router.
- `tests/steps/conftest.py` — mount version router in BDD app fixture.
- `TESTPLAN.md` — mark VERS-01..05 green when done.

## Step definition order (TDD)

1. `given_a_complete_wisp_version` / `given_an_in_progress_wisp_version`
2. `when_the_admin_exports_version_N`
3. `then_the_pdf_contains_DRAFT` / `then_the_pdf_does_not_contain_DRAFT`
4. `when_the_admin_starts_a_new_version`
5. `then_the_new_version_has_status_in_progress`
6. `then_the_previous_version_is_immutable` / `then_the_new_version_clones_approved_baseline`
7. `when_the_admin_starts_a_second_version` → `then_the_request_is_rejected`
8. `when_the_admin_exports_version_1` → `then_the_export_succeeds`

## Key design decisions

- PDF rendering uses **WeasyPrint** (approved dependency). The service builds an HTML string from a Jinja template and returns bytes. Tests inspect the returned bytes via `pdfminer.six` text extraction or a simple string search if we render text as SVG; if text extraction is unreliable, tests will assert on the HTML payload instead while still verifying the PDF endpoint returns `application/pdf`. **Open question:** do we need `pdfminer.six` as a dev dependency, or is byte-level substring search on the PDF sufficient? The spec says "watermark asserted by inspecting generated PDF text layer." I recommend adding `pdfminer.six` as a dev dependency for robust text-layer assertions.
- Versioning model: `wisp_versions` already has `tenant_id`, `number`, `status`, `created_at`, `completed_at`. A new version gets `number = max+1`, `status = in_progress`. Domains and assignments are cloned for the new version. Approved compiled answers and their underlying answers are copied; unapproved/in-progress domains start empty (per C-14 new baseline from approved work).
- Single-in-progress guard enforced in `start_new_version` before inserting (C-14).
- Prior version immutability: once `status = complete`, the service refuses to add/edit domains, questions, answers, or assignments for that version (enforced in version-aware writes). For export, prior versions remain readable.

## Dependencies

- `weasyprint` already listed in constitution approved list; verify it is in `pyproject.toml`.
- Request approval for `pdfminer.six` as a dev dependency if text-layer assertions are required.

## Verification

- `uv run pytest tests/steps/test_wisp_versioning_and_export.py -q` green for VERS-01..05.
- `uv run pytest tests/unit -q` green.
- `uv run pytest tests/ -q` green (no neighbor regressions).
- `uv run ruff check . && uv run ruff format --check .` clean.
- Update `TESTPLAN.md` VERS-01..05 → green.

## Open questions

1. Should the export endpoint accept `version_id` as path param or always export the current version? Plan uses `GET /versions/{id}/export` for explicit version targeting.
2. Does the new version clone assignments as well as answers? Plan: clone assignments only for approved domains; unapproved domains remain unassigned until admin assigns them.
3. Is `pdfminer.six` acceptable as a dev dependency for text-layer assertions?
