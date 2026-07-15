# Merge PRs, Cleanup, and User Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the open Task 19 and Task 20 PRs, clean up feature branches, and produce a user manual with screenshots in `docs/generated/user-manual.md`.

**Architecture:** Use `gh` to merge both PRs as squash merges, prune branches, run full verification on `main`, capture representative Playwright screenshots during a clean E2E run, and assemble a markdown user manual covering signup, login, domain questionnaire, review, user management, and version/export workflows.

**Tech Stack:** GitHub CLI, git, Playwright, Markdown.

## Global Constraints
- Only use `uv` for Python; never `pip`.
- Never call real LLM, Tavily, Stripe, or SES endpoints from tests.
- Do not edit `constitution.md` or weaken constraints C-01 through C-19.
- Generated docs belong in `docs/generated/`.
- One task per PR; cite task IDs in commits.

---

### Task 1: Merge Task 20 PR

**Files:**
- Modify: `main` branch (via GitHub merge)
- Command: `gh pr merge 1 --repo rapidarchitect/wisp_mvp --squash --delete-branch`

**Interfaces:**
- Consumes: PR #1 (`task-20-e2e-regression` → `main`)
- Produces: merged `main` with Task 20 changes

- [ ] **Step 1: Verify PR #1 is mergeable**

```bash
cd /Users/mikeh/Downloads/wisp_july_10
gh pr view 1 --repo rapidarchitect/wisp_mvp --json state,mergeStateStatus,title
```

Expected: `state` is `OPEN`, `mergeStateStatus` is `CLEAN` or `BLOCKED` (if checks missing).

- [ ] **Step 2: Squash-merge PR #1**

```bash
gh pr merge 1 --repo rapidarchitect/wisp_mvp --squash --delete-branch --subject "feat(task-20): full Playwright E2E regression suite, all scenario IDs green"
```

Expected: PR merged, branch deleted on remote.

- [ ] **Step 3: Pull main locally and confirm**

```bash
git checkout main
git pull origin main
git log --oneline -5 main
```

Expected: top commit is the Task 20 squash merge.

---

### Task 2: Merge Task 19 PR

**Files:**
- Modify: `main` branch (via GitHub merge)
- Command: `gh pr merge 2 --repo rapidarchitect/wisp_mvp --squash --delete-branch`

**Interfaces:**
- Consumes: PR #2 (`task-19-infrastructure` → `main`)
- Produces: merged `main` with Task 19 hardening changes

- [ ] **Step 1: Verify PR #2 is mergeable**

```bash
gh pr view 2 --repo rapidarchitect/wisp_mvp --json state,mergeStateStatus,title
```

Expected: PR is open.

- [ ] **Step 2: Squash-merge PR #2**

```bash
gh pr merge 2 --repo rapidarchitect/wisp_mvp --squash --delete-branch --subject "feat(task-19): harden EC2 bootstrap and deploy script, update docs"
```

Expected: PR merged, branch deleted on remote.

- [ ] **Step 3: Pull main and confirm history**

```bash
git checkout main
git pull origin main
git log --oneline -5 main
```

Expected: top two commits are Task 19 and Task 20 squash merges.

---

### Task 3: Clean Up Local Branches

**Files:**
- Delete local branches: `task-20-e2e-regression`, `task-19-infrastructure`, and any other merged feature branches.

**Interfaces:**
- Consumes: merged remote branches
- Produces: clean local branch list

- [ ] **Step 1: Delete local merged branches**

```bash
git checkout main
git branch -d task-20-e2e-regression
git branch -d task-19-infrastructure
```

Expected: branches removed without error.

- [ ] **Step 2: Prune stale remote tracking refs**

```bash
git remote prune origin
```

Expected: deleted remote tracking branches for merged PRs.

- [ ] **Step 3: List remaining branches**

```bash
git branch -a
```

Expected: only unmerged historical task branches and `main` remain.

---

### Task 4: Verify Main After Merges

**Files:**
- All project files on `main`

**Interfaces:**
- Consumes: merged codebase
- Produces: green verification results

- [ ] **Step 1: Run backend tests and lint**

```bash
uv run pytest tests/ -q
uv run ruff check .
uv run ruff format --check .
```

Expected: tests pass, lint/format clean.

- [ ] **Step 2: Build frontend**

```bash
cd frontend
npm run build
```

Expected: build succeeds (chunk-size warning only).

- [ ] **Step 3: Run Playwright E2E suite**

```bash
DOCKER_DEV=1 npx playwright test
```

Expected: 45 passed.

- [ ] **Step 4: Run Terraform plan dry-run**

```bash
cd ../infra
terraform plan -var="allowed_ssh_cidr=24.11.224.55/32" -out=/tmp/tfplan
```

Expected: plan succeeds with 13 resources to add.

---

### Task 5: Capture Screenshots for User Manual

**Files:**
- Create: screenshot images in `docs/generated/screenshots/`

**Interfaces:**
- Consumes: running Docker dev stack and Playwright browser contexts
- Produces: PNG screenshots of key workflows

- [ ] **Step 1: Ensure Docker dev stack is healthy**

```bash
cd /Users/mikeh/Downloads/wisp_july_10
docker compose up -d
docker compose exec backend uv run python frontend/e2e/setup.py
```

Expected: backend/frontend healthy, demo tenant seeded.

- [ ] **Step 2: Run a Playwright script to capture screenshots**

Create a temporary script `frontend/e2e/screenshot-flows.spec.ts` with page-level screenshots for:
- Signup page
- Login page
- Dashboard
- Admin users (pending invitation)
- Domain questionnaire (question answered)
- Review queue
- Versions/export page

```bash
cd frontend
DOCKER_DEV=1 npx playwright test e2e/screenshot-flows.spec.ts
```

Expected: screenshots written to `test-results/screenshots/`.

- [ ] **Step 3: Move screenshots to docs/generated/screenshots/**

```bash
mkdir -p docs/generated/screenshots
mv frontend/test-results/screenshots/*.png docs/generated/screenshots/
```

Expected: PNG files present in docs directory.

- [ ] **Step 4: Remove temporary screenshot spec**

```bash
rm frontend/e2e/screenshot-flows.spec.ts
```

---

### Task 6: Write User Manual

**Files:**
- Create: `docs/generated/user-manual.md`

**Interfaces:**
- Consumes: screenshots and application workflow knowledge
- Produces: markdown user manual

- [ ] **Step 1: Write manual sections**

Sections:
1. Introduction and audience
2. Creating an account (signup + voucher/card)
3. Logging in and TOTP setup
4. Dashboard overview
5. Inviting and managing users
6. Assigning contributors and reviewers to domains
7. Answering the questionnaire
8. Reviewing and approving domains
9. Exporting the WISP PDF
10. Version lifecycle

Each major workflow includes a screenshot from Task 5 and 3-6 paragraphs of plain-language explanation with concrete steps.

- [ ] **Step 2: Save the manual**

```bash
# File written via write tool in the step above
cat docs/generated/user-manual.md | head -50
```

Expected: manual exists and contains screenshots.

---

### Task 7: Final Commit and Push

**Files:**
- Create: `docs/generated/user-manual.md`, `docs/generated/screenshots/*.png`

**Interfaces:**
- Consumes: generated documentation
- Produces: committed docs on `main`

- [ ] **Step 1: Stage generated docs**

```bash
git add docs/generated/user-manual.md docs/generated/screenshots/
```

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: user manual with screenshots for signup, questionnaire, review, and export workflows"
```

- [ ] **Step 3: Push to main**

```bash
git push origin main
```

- [ ] **Step 4: Update session handoff**

Update `.claude/session-handoff.md` to note:
- PRs #1 and #2 merged.
- Branches cleaned.
- User manual published.
- All verification green.

```bash
git add .claude/session-handoff.md
git commit -m "docs(session-handoff): Task 19 and Task 20 merged, user manual published"
git push origin main
```

---

## Self-Review

1. **Spec coverage:** Merges cover Task 19 and Task 20; manual covers all end-user workflows.
2. **Placeholder scan:** No TBD or TODOs remain.
3. **Type consistency:** Not applicable (documentation/operations task).
4. **Risk:** Playwright screenshot run may fail if Docker dev stack is not healthy; plan includes a health check step.
