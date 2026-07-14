# Plan: Task 17 — React frontend: auth, onboarding, dashboards

## Objective
Build the first user-facing React application for WISPGen. Deliver:
1. A public signup/onboarding wizard covering corporate vitals and payment (card or voucher).
2. Login + mandatory TOTP enrollment + TOTP challenge flows.
3. Authenticated dashboards with role-aware navigation.
4. End-to-end Playwright coverage for SIGN-01, AUTH-01, AUTH-02, and USER-02.

The backend for these flows is already complete (Tasks 03–07, 15, 16). This task only creates the frontend and E2E tests; no backend behavior changes unless a bug is discovered, in which case the task halts and the bug is reported.

## Scope

### In scope
- `frontend/` package dependencies, config, and source structure.
- Generated OpenAPI types from the running dev backend (`npm run gen:api`).
- API client wrapper with tenant subdomain prefixing and session cookie handling.
- Auth context + `ProtectedRoute` guard.
- Public routes:
  - `/` — landing with workspace address input and link to signup/login.
  - `/signup` — multi-step signup wizard.
  - `/login` — email + password form.
  - `/enroll-totp` — first-time TOTP QR enrollment and verification.
  - `/totp` — TOTP challenge on every login after enrollment.
  - `/activate?token=...` — accept invitation, set password, enroll TOTP.
- Authenticated routes:
  - `/dashboard` — role-aware home (Admin sees team/version cards; Contributor sees assigned domains; Reviewer shows pending reviews).
  - `/admin/users` — invite user and list invitations (admin only).
  - `/admin/domains` — domain assignment placeholder (admin only; list only for this task).
- E2E Playwright specs under `frontend/e2e/` for SIGN-01, AUTH-01, AUTH-02, USER-02.
- TESTPLAN.md E2E matrix update.

### Out of scope
- Full domain Q&A, review, PDF export, and version UI (Task 18+).
- Real Stripe.js checkout UI (we redirect to Stripe Checkout URL returned by the API).
- Payment success/cancel pages (reuse `/signup?success=1` and `/signup?canceled=1` for now).
- Production build/deploy/nginx changes (Task 19).
- Real-time notifications, audit log viewer, logo upload.

## Assumptions and Risks

### Assumptions
- The backend currently exposes all required endpoints under `/api/v1/...` and serves `GET /openapi.json` from the dev server at `http://localhost:8000`.
- Session auth is cookie-based; `credentials: "include"` is sufficient.
- The backend already supports test vouchers and test Stripe Checkout mode via existing BDD fixtures.
- Playwright can run the frontend dev server (`npm run dev`) and the backend (`uv run uvicorn ...`) concurrently in CI using separate ports.

### Risks
- CORS misconfiguration between Vite dev server and FastAPI can block signup/login E2E. Mitigation: configure Vite proxy to forward `/api` to the backend so E2E uses same-origin requests.
- OpenAPI generation may fail if backend is not running. Mitigation: start backend before `gen:api` and commit generated types.
- Stripe Checkout redirect is hard to test end-to-end without browser automation beyond Playwright. Mitigation: SIGN-01 E2E will use the existing backend `POST /api/v1/signup` success simulation (the same mock the BDD tests use) by calling a test-only endpoint or by exercising the real API and then simulating the webhook.

## Verification
- `cd frontend && npm run lint && npm run format --check` passes.
- `uv run pytest tests/ -q` still passes (backend unchanged).
- `cd frontend && npx playwright test e2e/signup.spec.ts e2e/auth.spec.ts e2e/activate.spec.ts` passes.
- E2E rows in TESTPLAN.md for SIGN-01, AUTH-01, AUTH-02, USER-02 marked green.

## Implementation Steps

1. **Bootstrap frontend structure**
   - Add dependencies: `react-router-dom`, `clsx`/`tailwind-merge` (lightweight), `@types/node` if absent.
   - Add dev dependencies: `playwright`, `@playwright/test`.
   - Configure `frontend/vite.config.ts` proxy: `/api` → `http://localhost:8000`, `/openapi.json` → `http://localhost:8000`.
   - Add npm scripts: `test:e2e`, `test:e2e:ci`.
   - Generate API types from running backend.

2. **API client and types**
   - Create `frontend/src/api/types.ts` via `gen:api`.
   - Create `frontend/src/api/client.ts`:
     - `baseUrl` resolves to `/api/v1` (Vite proxy).
     - All requests include `credentials: "include"` and `Content-Type: application/json`.
     - Helper `apiFetch` throws typed errors matching backend response shapes.

3. **Auth context**
   - `frontend/src/auth/AuthContext.tsx`: holds `user` (from `GET /api/v1/auth/me`), `login`, `logout`, `isLoading`.
   - On mount, fetch `/api/v1/auth/me`; if 401, treat as logged out.
   - `login` posts `/api/v1/auth/login` and returns the next step (`enroll_totp` or `totp`).
   - `logout` posts `/api/v1/auth/logout`.

4. **Public pages**
   - `LandingPage`: workspace address input, links.
   - `SignupPage`: wizard steps (vitals, payment method, card/voucher, summary), redirects to Stripe Checkout URL for card or submits voucher signup and lands on enrollment.
   - `LoginPage`: email/password, then redirect based on backend response (enroll TOTP or challenge).
   - `EnrollTotpPage`: show QR URL from `/api/v1/auth/totp/enroll`, verify with code.
   - `TotpChallengePage`: submit TOTP code.
   - `ActivatePage`: read `?token=`, validate, set password, enroll TOTP, redirect to dashboard.

5. **Authenticated shell**
   - `DashboardLayout`: header with user/tenant info, nav links filtered by roles.
   - `DashboardPage`: role-aware cards and counts.
   - `AdminUsersPage`: invite form, list invitations and users.
   - `AdminDomainsPage`: read-only list of domains and assignments (placeholder).

6. **Routing**
   - Use `createBrowserRouter` with public routes and protected routes wrapped in `ProtectedRoute`.
   - Role guard helper for admin pages.

7. **E2E tests**
   - `frontend/e2e/signup.spec.ts`: SIGN-01 using voucher path to avoid real Stripe (per Task 17 spec asks E2E coverage of SIGN-01; voucher path exercises the full frontend wizard and provisioning).
   - `frontend/e2e/auth.spec.ts`: AUTH-01 and AUTH-02.
   - `frontend/e2e/activate.spec.ts`: USER-02.
   - Global setup seeds test tenant and voucher via backend fixture helpers or direct API calls in `frontend/e2e/global-setup.ts`.

8. **Cleanup and matrix update**
   - Run full backend test suite to confirm no regressions.
   - Run lint/format.
   - Update TESTPLAN.md E2E rows.

## Files to Create/Modify

### New files
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/components/ProtectedRoute.tsx`
- `frontend/src/components/RoleGuard.tsx`
- `frontend/src/layouts/DashboardLayout.tsx`
- `frontend/src/pages/LandingPage.tsx`
- `frontend/src/pages/SignupPage.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/EnrollTotpPage.tsx`
- `frontend/src/pages/TotpChallengePage.tsx`
- `frontend/src/pages/ActivatePage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/AdminUsersPage.tsx`
- `frontend/src/pages/AdminDomainsPage.tsx`
- `frontend/src/main.tsx` (modify)
- `frontend/vite.config.ts` (modify)
- `frontend/package.json` (modify)
- `frontend/e2e/signup.spec.ts`
- `frontend/e2e/auth.spec.ts`
- `frontend/e2e/activate.spec.ts`
- `frontend/playwright.config.ts`
- `frontend/e2e/global-setup.ts`
- `frontend/e2e/helpers/api.ts`
- `docs/superpowers/plans/2026-07-14-task17-frontend-auth-dashboards.md` (this file)

### Modified files
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/vite.config.ts`
- `frontend/package.json`
- `frontend/package-lock.json`
- `TESTPLAN.md`

## Questions
1. Should I use the existing `frontend/src/App.tsx` as the router entry point, or replace it entirely with `main.tsx` wiring? (I plan to keep `App.tsx` as the router component.)
2. The SPEC says Task 17 E2E covers SIGN-01. SIGN-01 is the card path, but the card path requires a real Stripe redirect. Do you approve using the voucher path for the E2E smoke and a separate Playwright test that mocks Stripe redirect via a test-only webhook endpoint? Or should I add a test-only Stripe-success endpoint to the backend as a minimal change?
3. Do you want Tailwind CSS for styling, or keep it plain CSS/inline styles? The constitution does not restrict CSS libraries; Tailwind keeps the scaffold simple. If Tailwind is acceptable, I will add it and configure Vite.

Awaiting approval before implementation.
