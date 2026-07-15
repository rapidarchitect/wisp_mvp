# PR-B: Card-based dashboard, domain assignment, and review queue UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the dashboard, admin domain assignment, and reviewer queue into card-based, action-oriented UIs while keeping all existing E2E scenarios green.

**Architecture:** Keep the existing page/routing structure and API contracts; only change presentation. Dashboard will show role-aware summary cards, admin domains will become assignable cards with contributor/reviewer selects, and the review queue will be a filterable card grid. Each card keeps `data-domain-code` and adds stable `data-testid`s so E2E selectors remain valid.

**Tech Stack:** React 18, Vite, Material UI 5, React Router 6, TypeScript, existing `apiFetch` helper.

## Global Constraints

- Only the constitution-approved dependency list; no new packages.
- Keep existing API endpoints and response shapes.
- Preserve all existing `data-domain-code` attributes used by E2E.
- Add `data-testid` attributes for new UI elements; do not remove old ones.
- Run `npm run build` and the affected E2E specs after every task.
- Never skip or weaken failing tests.

---

### Task 1: Redesign `DashboardPage.tsx` as role-aware card dashboard

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Test: `frontend/e2e/auth.spec.ts` (login flow expects Dashboard heading)

**Interfaces:**
- Consumes: `GET /api/v1/domains/assigned` returns `Assignment[]` (`{ code, name, status }`); `useAuth()` returns user with `roles`.
- Produces: Same page component, same route `/dashboard`, same page heading "Dashboard".

- [ ] **Step 1: Write the failing build/selector check**

```bash
cd frontend
npm run build
```

Expected: passes with current code.

- [ ] **Step 2: Replace the list UI with summary + status cards**

Current `DashboardPage.tsx` renders a single card with a `List` of assignments. Replace it with:

```tsx
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Grid,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

type Assignment = {
  code: string;
  name: string;
  status: string;
};

const statusOrder: Record<string, number> = {
  pending_questions: 0,
  assigned: 1,
  in_progress: 2,
  in_review: 3,
  approved: 4,
};

const statusColor: Record<string, "default" | "primary" | "warning" | "success" | "info"> = {
  pending_questions: "default",
  assigned: "info",
  in_progress: "primary",
  in_review: "warning",
  approved: "success",
};

export function DashboardPage() {
  const { state } = useAuth();
  const user = state.status === "authenticated" ? state.user : null;
  const navigate = useNavigate();

  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    apiFetch<Assignment[]>("/domains/assigned")
      .then(setAssignments)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load assignments"),
      );
  }, [user]);

  const sorted = useMemo(
    () =>
      (assignments ?? []).slice().sort((a, b) => {
        const ao = statusOrder[a.status] ?? 99;
        const bo = statusOrder[b.status] ?? 99;
        if (ao !== bo) return ao - bo;
        return a.name.localeCompare(b.name);
      }),
    [assignments],
  );

  const isAdmin = user?.roles.includes("admin");
  const isContributor = user?.roles.includes("contributor");
  const isReviewer = user?.roles.includes("reviewer");

  const ctaPath = isReviewer
    ? "/review"
    : isContributor
      ? "/domains"
      : isAdmin
        ? "/admin/users"
        : "/";

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      {user && (
        <Typography variant="body1" sx={{ mb: 3 }}>
          Welcome, {user.email}. Roles: {user.roles.join(", ")}.
        </Typography>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {assignments === null && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {assignments !== null && sorted.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No domain assignments yet.
          {isAdmin && " Use the Domains page to assign contributors and reviewers."}
        </Alert>
      )}
      {assignments !== null && (
        <>
          {isReviewer && (
            <Box sx={{ mb: 3 }}>
              <Button
                variant="contained"
                onClick={() => navigate("/review")}
                data-testid="dashboard-review-queue-cta"
              >
                Go to review queue
              </Button>
            </Box>
          )}
          {isContributor && (
            <Box sx={{ mb: 3 }}>
              <Button
                variant="contained"
                onClick={() => navigate("/domains")}
                data-testid="dashboard-my-domains-cta"
              >
                My domains
              </Button>
            </Box>
          )}
          {isAdmin && !isReviewer && !isContributor && (
            <Box sx={{ mb: 3 }}>
              <Button
                variant="contained"
                onClick={() => navigate("/admin/domains")}
                data-testid="dashboard-admin-domains-cta"
              >
                Manage domains
              </Button>
            </Box>
          )}
          <Grid container spacing={2}>
            {sorted.map((a) => (
              <Grid item xs={12} sm={6} md={4} key={a.code}>
                <Card variant="outlined" data-domain-code={a.code} data-testid={`dashboard-card-${a.code}`}>
                  <CardContent>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography variant="h6">
                        {a.name} ({a.code})
                      </Typography>
                      <Chip label={a.status.replace(/_/g, " ")} color={statusColor[a.status] ?? "default"} size="small" />
                    </Box>
                  </CardContent>
                  <CardActions>
                    <Button size="small" onClick={() => navigate(ctaPath)}>
                      Open
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Run build and auth E2E**

```bash
cd frontend
npm run build
DOCKER_DEV=1 npx playwright test e2e/auth.spec.ts
```

Expected: build passes, auth spec passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx
git commit -m "feat(pr-b): redesign dashboard as role-aware card grid (C-01)"
```

---

### Task 2: Redesign `AdminDomainsPage.tsx` as assignable card grid

**Files:**
- Modify: `frontend/src/pages/AdminDomainsPage.tsx`
- Test: `frontend/e2e/domain-assignment.spec.ts` (ASSN-01 through ASSN-05 are API-only; add one UI test), `frontend/e2e/review.spec.ts`

**Interfaces:**
- Consumes: `GET /api/v1/domains/unassigned` returns `Domain[]` (`{ code, name, status, contributor_email?, reviewer_email? }`); `GET /api/v1/users` returns `User[]` (`{ id, email, roles, status }`). `POST /api/v1/domains/{code}/assign` body `{ contributor_email, reviewer_email }`.
- Produces: Same page component/route. Adds `data-testid` selectors.

- [ ] **Step 1: Add UI-driven domain assignment test**

Append to `frontend/e2e/domain-assignment.spec.ts`:

```ts
test("admin assigns domain through UI (ASSN-06)", async ({ page }) => {
  const adminToken = await login("admin@demo.example.com");
  await loginAsApi(page, "admin@demo.example.com", TOTP_URI);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  await page.getByRole("link", { name: "Domains" }).click();
  await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();

  const domainCard = page.getByTestId("domain-card-PE");
  await expect(domainCard).toBeVisible();

  await domainCard.getByLabel("Contributor").click();
  await page.getByRole("option", { name: "contributor@demo.example.com" }).click();
  await page.keyboard.press("Escape");

  await domainCard.getByLabel("Reviewer").click();
  await page.getByRole("option", { name: "reviewer@demo.example.com" }).click();
  await page.keyboard.press("Escape");

  await domainCard.getByRole("button", { name: "Assign" }).click();

  await expect(domainCard).toContainText("contributor@demo.example.com", { timeout: 10000 });
  await expect(domainCard).toContainText("reviewer@demo.example.com");
});
```

Import `loginAsApi` and `TOTP_URI` helper as needed. Add at top of file:

```ts
import { loginAsApi } from "./api";
import { generateTotpCodeFromUri } from "./helpers";

const TOTP_URI = "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";
```

Run the new test; expect it to fail because the UI does not yet expose assignment controls.

```bash
cd frontend
DOCKER_DEV=1 npx playwright test e2e/domain-assignment.spec.ts -g "ASSN-06"
```

- [ ] **Step 2: Rewrite `AdminDomainsPage.tsx` with assignment cards**

Replace the component with a card grid. Each card shows the domain name/code, current assignments (if any), two `Select` inputs filtered to users with the matching role, and an `Assign` button.

```tsx
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_email?: string;
  reviewer_email?: string;
};

type User = {
  id: number;
  email: string;
  roles: string[];
  status: string;
};

export function AdminDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [picks, setPicks] = useState<Record<string, { contributor?: string; reviewer?: string }>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const loadDomains = () => {
    apiFetch<Domain[]>("/domains/unassigned")
      .then((rows) => {
        setDomains(rows);
        const init: Record<string, { contributor?: string; reviewer?: string }> = {};
        for (const d of rows) {
          init[d.code] = { contributor: d.contributor_email, reviewer: d.reviewer_email };
        }
        setPicks(init);
      })
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load domains"),
      );
  };

  const loadUsers = () => {
    apiFetch<User[]>("/users")
      .then(setUsers)
      .catch((err) =>
        setError(err instanceof ApiResponseError ? err.error.message : "Failed to load users"),
      );
  };

  useEffect(() => {
    loadDomains();
    loadUsers();
  }, []);

  const assign = async (code: string) => {
    const { contributor, reviewer } = picks[code] ?? {};
    if (!contributor || !reviewer) {
      setError("Select both a contributor and a reviewer.");
      return;
    }
    setSaving((s) => ({ ...s, [code]: true }));
    setError(null);
    try {
      await apiFetch(`/domains/${code}/assign`, {
        method: "POST",
        body: { contributor_email: contributor, reviewer_email: reviewer },
      });
      loadDomains();
    } catch (err) {
      const message = err instanceof ApiResponseError ? err.error.message : "Assignment failed";
      setError(message);
    } finally {
      setSaving((s) => ({ ...s, [code]: false }));
    }
  };

  const candidates = (role: string) =>
    (users ?? []).filter((u) => u.status === "active" && u.roles.includes(role));

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Domains
      </Typography>
      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      {domains === null && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {domains !== null && (
        <Grid container spacing={2}>
          {domains.map((d) => (
            <Grid item xs={12} md={6} lg={4} key={d.code}>
              <Card variant="outlined" data-testid={`domain-card-${d.code}`} data-domain-code={d.code}>
                <CardContent>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                    <Typography variant="h6">
                      {d.name} ({d.code})
                    </Typography>
                    <Chip label={d.status.replace(/_/g, " ")} size="small" />
                  </Box>
                  <Box sx={{ display: "grid", gap: 2, mt: 2 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel id={`contributor-label-${d.code}`}>Contributor</InputLabel>
                      <Select
                        labelId={`contributor-label-${d.code}`}
                        value={picks[d.code]?.contributor ?? ""}
                        label="Contributor"
                        onChange={(e) =>
                          setPicks((p) => ({
                            ...p,
                            [d.code]: { ...p[d.code], contributor: e.target.value as string },
                          }))
                        }
                      >
                        {candidates("contributor").map((u) => (
                          <MenuItem key={u.id} value={u.email}>
                            {u.email}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl fullWidth size="small">
                      <InputLabel id={`reviewer-label-${d.code}`}>Reviewer</InputLabel>
                      <Select
                        labelId={`reviewer-label-${d.code}`}
                        value={picks[d.code]?.reviewer ?? ""}
                        label="Reviewer"
                        onChange={(e) =>
                          setPicks((p) => ({
                            ...p,
                            [d.code]: { ...p[d.code], reviewer: e.target.value as string },
                          }))
                        }
                      >
                        {candidates("reviewer").map((u) => (
                          <MenuItem key={u.id} value={u.email}>
                            {u.email}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </CardContent>
                <CardActions>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={
                      saving[d.code] ||
                      !picks[d.code]?.contributor ||
                      !picks[d.code]?.reviewer
                    }
                    onClick={() => assign(d.code)}
                  >
                    {saving[d.code] ? "Saving..." : "Assign"}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Run build and domain-assignment E2E**

```bash
cd frontend
npm run build
DOCKER_DEV=1 npx playwright test e2e/domain-assignment.spec.ts
```

Expected: build passes; ASSN-01 through ASSN-06 pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminDomainsPage.tsx frontend/e2e/domain-assignment.spec.ts
git commit -m "feat(pr-b): assignable card grid for admin domains (C-01)"
```

---

### Task 3: Redesign `ReviewerDomainsPage.tsx` as review queue with status filter

**Files:**
- Modify: `frontend/src/pages/ReviewerDomainsPage.tsx`
- Test: `frontend/e2e/review.spec.ts`

**Interfaces:**
- Consumes: `GET /api/v1/domains/assigned` returns `Domain[]` (`{ code, name, status, contributor_id?, reviewer_id? }`).
- Produces: Same page component/route. Keeps `data-domain-code` and adds `data-testid`.

- [ ] **Step 1: Rewrite `ReviewerDomainsPage.tsx` with filter tabs and richer cards**

```tsx
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, ApiResponseError } from "../api/client";

type Domain = {
  code: string;
  name: string;
  status: string;
  contributor_id?: number;
  reviewer_id?: number;
};

const filters = ["all", "in_review", "approved"];

const statusColor: Record<string, "default" | "primary" | "warning" | "success" | "info"> = {
  in_review: "warning",
  approved: "success",
};

export function ReviewerDomainsPage() {
  const [domains, setDomains] = useState<Domain[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const navigate = useNavigate();

  useEffect(() => {
    apiFetch<Domain[]>("/domains/assigned")
      .then((rows) =>
        setDomains(rows.filter((d) => d.status === "in_review" || d.status === "approved")),
      )
      .catch((err) =>
        setError(
          err instanceof ApiResponseError ? err.error.message : "Failed to load assignments",
        ),
      );
  }, []);

  const filtered = useMemo(() => {
    if (domains === null) return null;
    if (filter === "all") return domains;
    return domains.filter((d) => d.status === filter);
  }, [domains, filter]);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Review queue
      </Typography>
      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}
      {domains === null && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {domains !== null && (
        <>
          <Tabs value={filter} onChange={(_, v) => setFilter(v)} sx={{ mb: 2 }}>
            {filters.map((f) => (
              <Tab
                key={f}
                value={f}
                label={f.replace(/_/g, " ")}
                data-testid={`review-filter-${f}`}
              />
            ))}
          </Tabs>
          {filtered!.length === 0 && (
            <Typography>No domains in this queue.</Typography>
          )}
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
            {filtered!.map((d) => (
              <Card key={d.code} data-domain-code={d.code} data-testid={`review-card-${d.code}`}>
                <CardActionArea onClick={() => navigate(`/review/${d.code}`)}>
                  <CardContent>
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography variant="h6">
                        {d.name} ({d.code})
                      </Typography>
                      <Chip label={d.status.replace(/_/g, " ")} color={statusColor[d.status] ?? "default"} size="small" />
                    </Box>
                    <Button size="small" variant="outlined" sx={{ mt: 1 }}>
                      Review
                    </Button>
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Box>
        </>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Run build and review E2E**

```bash
cd frontend
npm run build
DOCKER_DEV=1 npx playwright test e2e/review.spec.ts
```

Expected: build passes; REVW-01 through REVW-05 pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReviewerDomainsPage.tsx
git commit -m "feat(pr-b): filterable review queue card grid (C-01)"
```

---

### Task 4: Full PR-B verification

**Files:**
- Modify: none (verification only).
- Test: all affected specs plus build/lint.

- [ ] **Step 1: Run full frontend checks**

```bash
cd frontend
npm run build
npx playwright test e2e/auth.spec.ts e2e/domain-assignment.spec.ts e2e/review.spec.ts
```

Expected: all pass.

- [ ] **Step 2: Run backend regression**

```bash
cd /Users/mikeh/Downloads/wisp_july_10
uv run pytest tests/ -q
uv run ruff check .
uv run ruff format --check .
```

Expected: all pass.

- [ ] **Step 3: Commit verification notes / update TESTPLAN.md**

No code changes remain; if TESTPLAN.md traceability matrix lists UI tasks, mark the relevant rows as passed. Otherwise skip.

```bash
git add TESTPLAN.md  # only if updated
git commit -m "docs(pr-b): update traceability matrix"
```

---

## Self-Review

1. **Spec coverage:** The request was "card-based dashboard/domain assignment/review queue". Each of the three pages gets a dedicated task. The dashboard gains role-aware CTAs. Domain assignment becomes UI-driven. Review queue gets filterable cards.
2. **Placeholder scan:** No TBD/TODO. Each step contains code/commands.
3. **Type consistency:** Uses existing `Domain`, `User`, and `Assignment` shapes from current code. `apiFetch` calls match existing endpoints.
4. **E2E compatibility:** Existing `data-domain-code` attributes are preserved. New tests use `data-testid` selectors. No existing selectors are removed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-15-pr-b-dashboard-domains-review.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
