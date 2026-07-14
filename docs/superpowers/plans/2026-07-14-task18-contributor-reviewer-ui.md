# Plan: Task 18 — Contributor and reviewer UI

## Objective
Extend the Task 17 React frontend with the contributor questionnaire, reviewer review, and admin export/version screens. Deliver Playwright E2E coverage for:
- QSTN-01 — answering a question generates follow-ups.
- QSTN-02 — AI compiles the domain final answer.
- REVW-01 — reviewer approves a compiled answer.
- REVW-02 — reviewer edits and AI revises, then directly approves.
- VERS-01 — draft export carries DRAFT watermark.
- VERS-02 — complete WISP exports clean PDF.

The backend endpoints for these flows already exist (Tasks 13–16). This task adds only frontend pages and E2E tests; backend changes are limited to small test-only helpers if the E2E suite needs them.

## Scope

### In scope
- Contributor pages:
  - `/domains` — list of domains assigned to the current user with status badges and progress.
  - `/domains/:code` — domain questionnaire: list questions, answer yes/no, skip, respond to follow-ups, compile, submit.
- Reviewer pages:
  - `/review` — list of domains in review assigned to the current reviewer.
  - `/review/:code` — read compiled narrative, approve, defer, or request AI revision with prompt and approve.
- Admin pages:
  - `/admin/versions` — list WISP versions, start new version, download PDF for current/prior versions.
  - `/admin/export` — quick export of current version PDF.
- Shared UI: notifications indicator in the dashboard header, error/loading states.
- E2E specs under `frontend/e2e/`:
  - `questionnaire.spec.ts` — QSTN-01 and QSTN-02.
  - `review.spec.ts` — REVW-01 and REVW-02.
  - `versions.spec.ts` — VERS-01 and VERS-02.
- `TESTPLAN.md` E2E matrix update for QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02.

### Out of scope
- Real-time notifications, email, audit-log viewer.
- Mobile/responsive polish beyond basic MUI grid breakpoints.
- Logo upload, company settings, user deactivation UI.
- Production deploy/nginx changes (Task 19).

## Assumptions and risks

### Assumptions
- Backend endpoints already work as documented in generated `frontend/src/api/types.ts`.
- The demo tenant E2E seed has at least one domain with seeded questions and contributor/reviewer assignments. If not, we will extend `frontend/e2e/setup.py` to seed a fully prepared domain for the questionnaire/review tests.
- `LLM_PROVIDER=fake` in Playwright webServer config provides deterministic follow-ups and compilation, making E2E assertions stable.

### Risks
- E2E for QSTN-01 depends on fake LLM returning follow-ups. If the fake crew returns empty follow-ups, the test can assert the follow-up state instead of rendered follow-up count.
- PDF export in E2E returns binary bytes; we can assert the download filename and status, and optionally inspect the PDF text with `pdfjs-dist` or a backend test endpoint.
- Starting a new version in VERS-02 needs a completed version first, which requires one approved domain. We will use the seeded demo domain and fake reviewer flow to set this up quickly.

## Implementation steps

1. **Seed E2E data**
   - Extend `frontend/e2e/setup.py` to assign one domain (e.g., `AC`) to the demo contributor and reviewer and seed a few questions so the contributor can answer immediately.

2. **Contributor domain list**
   - Create `frontend/src/pages/ContributorDomainsPage.tsx`.
   - Call `GET /api/v1/domains/assigned` and render cards with status, name, and progress.

3. **Contributor questionnaire page**
   - Create `frontend/src/pages/DomainQuestionnairePage.tsx`.
   - Load `GET /api/v1/domains/{code}/progress`.
   - Render questions with yes/no/skip actions and follow-up response inputs.
   - Call `POST /api/v1/questions/{id}/answer` and `POST /api/v1/followups/{id}/respond`.
   - Show compile button when `submit_ready` is true; call `POST /api/v1/domains/{code}/compile`.
   - Show submit button after compile; call `POST /api/v1/domains/{code}/submit`.

4. **Reviewer domain list**
   - Create `frontend/src/pages/ReviewerDomainsPage.tsx`.
   - Load assigned domains filtered to `in_review` status.

5. **Reviewer detail page**
   - Create `frontend/src/pages/ReviewDomainPage.tsx`.
   - Load domain progress (compiled answer narrative visible).
   - Buttons: Approve (`POST /api/v1/domains/{code}/approve`), Defer (`POST /api/v1/domains/{code}/defer`), Revise with prompt (`POST /api/v1/domains/{code}/revise`).

6. **Admin versions/export page**
   - Extend `frontend/src/pages/AdminVersionsPage.tsx`.
   - Load `GET /api/v1/versions`.
   - Buttons: export current PDF, export prior version PDF, start new version.

7. **Navigation**
   - Update `DashboardLayout.tsx` to show contributor/reviewer/admin nav links based on roles.
   - Update `App.tsx` with new routes.

8. **E2E tests**
   - `questionnaire.spec.ts`: log in as contributor, answer a question, assert follow-ups appear, respond to follow-ups, compile, assert narrative non-empty.
   - `review.spec.ts`: log in as reviewer, approve a submitted domain, then revise another with prompt and assert approval.
   - `versions.spec.ts`: log in as admin, export current version and assert DRAFT; set up one approved domain, export again and assert no DRAFT.

9. **Verification and matrix update**
   - `npm run build` passes.
   - `uv run pytest tests/ -q` still passes.
   - `npx playwright test e2e/questionnaire.spec.ts e2e/review.spec.ts e2e/versions.spec.ts --workers=1` passes.
   - Update `TESTPLAN.md`.

## Files to create or modify

### New files
- `frontend/src/pages/ContributorDomainsPage.tsx`
- `frontend/src/pages/DomainQuestionnairePage.tsx`
- `frontend/src/pages/ReviewerDomainsPage.tsx`
- `frontend/src/pages/ReviewDomainPage.tsx`
- `frontend/src/pages/AdminVersionsPage.tsx`
- `frontend/e2e/questionnaire.spec.ts`
- `frontend/e2e/review.spec.ts`
- `frontend/e2e/versions.spec.ts`
- This plan file

### Modified files
- `frontend/src/App.tsx`
- `frontend/src/layouts/DashboardLayout.tsx`
- `frontend/e2e/setup.py`
- `TESTPLAN.md`

## Questions
1. Should the questionnaire E2E assert actual follow-up text from the fake LLM, or is asserting the follow-up count/state sufficient? (I recommend count/state for stability.)
2. For VERS-01/VERS-02, do you want the E2E to parse the PDF text layer in the browser, or assert download response headers and rely on backend tests for watermark content? (I recommend backend watermark assertions already green + frontend download assertion.)
3. Should reviewer defer (REVW-03) and self-review warning (REVW-04) get frontend UI coverage in this task, or only the four scenarios listed in the spec plus the two version export scenarios? (The spec says E2E: QSTN-01, QSTN-02, REVW-01, REVW-02, VERS-01, VERS-02; I will stick to those.)

Awaiting approval before implementation.
