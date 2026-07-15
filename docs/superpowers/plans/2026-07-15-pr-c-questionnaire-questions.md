# PR-C: Stepped contributor questionnaire UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scroll-all-questions contributor questionnaire with a stepped wizard: one question per step, previous/next navigation, persistent progress indicator, and a final review/summary step before compile/submit.

**Architecture:** Keep the existing page component and route (`/domains/:code`). Reuse the existing `/domains/:code/progress`, `/questions/:id/answer`, `/followups/:id/respond`, `/domains/:code/compile`, and `/domains/:code/submit` API calls. Internally manage a `currentStep` index. Each answer/follow-up still persists immediately so progress is preserved on navigation/reload. The existing E2E selectors (`data-question`, `data-choice="yes"`, `data-answered="true"`, `data-followup`, `data-testid="answer-all"`, `data-testid="compiled-narrative"`) must be preserved.

**Tech Stack:** React 18, Vite, Material UI 5, React Router 6, TypeScript, existing `apiFetch` helper.

## Global Constraints

- Only the constitution-approved dependency list; no new packages.
- Keep existing API endpoints and response shapes.
- Preserve existing `data-question`, `data-choice`, `data-answered`, `data-followup`, and `data-testid` attributes used by E2E.
- Add `data-testid` attributes for new stepper elements; do not remove old ones.
- Run `npm run build` and the affected E2E specs after every task.
- Never skip or weaken failing tests.

---

### Task 1: Add a stepped UI to `DomainQuestionnairePage.tsx`

**Files:**
- Modify: `frontend/src/pages/DomainQuestionnairePage.tsx`
- Test: `frontend/e2e/questionnaire.spec.ts`

**Interfaces:**
- Consumes: `Progress` shape (`code, name, status, questions[], submit_ready`). Each `Question` has `id, text, position, answer`. `Answer` has `value, skipped, followups_state, followups[]`. `FollowUp` has `id, text, response_text`.
- Produces: Same page component/route. Adds `data-testid` selectors for the stepper and step controls.

- [ ] **Step 1: Build the stepped layout skeleton**

Replace the rendering section of `DomainQuestionnairePage.tsx` with a stepper UI. Keep all existing async functions (`answerQuestion`, `skipQuestion`, `respondFollowup`, `answerAll`, `compile`, `submit`) and the `Progress` types unchanged. Add state:

```ts
const [currentStep, setCurrentStep] = useState(0);
```

Add helper:

```ts
const activeQuestions = useMemo(
  () => progress?.questions ?? [],
  [progress],
);
const allAnswered = useMemo(
  () =>
    activeQuestions.length > 0 &&
    activeQuestions.every(
      (q) => q.answer && (!q.answer.skipped || true),
    ),
  [activeQuestions],
);
```

(Note: `skipped` counts as answered for progression, since the backend treats it as a response.)

- [ ] **Step 2: Render the active question card**

Inside the page render, replace the `progress.questions.map(...)` block with a single question card controlled by `currentStep`:

```tsx
const q = activeQuestions[currentStep];
```

Render the same answer/follow-up/skip UI as before for that single `q`, wrapped in a `Card` with `data-question={q.id}`. The `data-choice="yes"`, `data-choice="no"`, `data-answered="true"`, and `data-followup={f.id}` attributes must remain exactly as in the current code.

Add a step summary line above the card:

```tsx
<Typography variant="body2" color="text.secondary" sx={{ mb: 2 }} data-testid="step-indicator">
  Question {currentStep + 1} of {activeQuestions.length}
</Typography>
```

- [ ] **Step 3: Add Previous/Next navigation**

After the active question card, add navigation buttons:

```tsx
<Box sx={{ display: "flex", justifyContent: "space-between", mt: 2, mb: 2 }}>
  <Button
    variant="outlined"
    disabled={currentStep === 0}
    onClick={() => setCurrentStep((s) => s - 1)}
    data-testid="prev-step"
  >
    Previous
  </Button>
  <Button
    variant="outlined"
    disabled={currentStep === activeQuestions.length - 1}
    onClick={() => setCurrentStep((s) => s + 1)}
    data-testid="next-step"
  >
    Next
  </Button>
</Box>
```

- [ ] **Step 4: Add a linear progress bar**

Add a `LinearProgress` component above the step indicator:

```tsx
import { LinearProgress } from "@mui/material";
// ...
<LinearProgress
  variant="determinate"
  value={
    activeQuestions.length === 0
      ? 0
      : ((currentStep + 1) / activeQuestions.length) * 100
  }
  sx={{ mb: 2 }}
  data-testid="question-progress"
/>
```

- [ ] **Step 5: Add summary/review panel**

When `currentStep === activeQuestions.length - 1` and all questions have answers, show a collapsible summary card listing each question with its answer/follow-up status. This is optional; the minimum is to keep the existing `Compile` and `Submit for review` buttons at the bottom.

Keep the bottom action bar with `Compile`, `Submit for review`, and `Answer all remaining questions` buttons exactly where they are now, preserving their existing selectors.

- [ ] **Step 6: Run build and questionnaire E2E**

```bash
cd frontend
npm run build
DOCKER_DEV=1 npx playwright test e2e/questionnaire.spec.ts
```

Expected: build passes; QSTN-01 through QSTN-06 pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/mikeh/Downloads/wisp_july_10
git add frontend/src/pages/DomainQuestionnairePage.tsx
git commit -m "feat(pr-c): stepped contributor questionnaire UI (C-01)"
```

---

### Task 2: Ensure resume and navigation work with the stepper

**Files:**
- Modify: none (verification only).
- Test: `frontend/e2e/questionnaire.spec.ts` (QSTN-05 save and resume)

- [ ] **Step 1: Run resume test explicitly**

```bash
cd frontend
DOCKER_DEV=1 npx playwright test e2e/questionnaire.spec.ts -g "QSTN-05"
```

Expected: passes. The existing test expects `data-answered="true"` on the first card; with the stepper, the first card is still rendered on step 0, so the selector must still resolve.

If it fails because the answered state is hidden on another step, adjust the initial `currentStep` to default to the first unanswered question, or keep it at 0. The existing test navigates away and back, so defaulting to 0 is safe.

- [ ] **Step 2: Commit any required fix**

```bash
cd /Users/mikeh/Downloads/wisp_july_10
git add frontend/src/pages/DomainQuestionnairePage.tsx
git commit -m "fix(pr-c): keep answered first question visible on resume (C-01)"
```

---

### Task 3: Full PR-C verification

**Files:**
- Modify: none (verification only).
- Test: all affected specs plus build/lint.

- [ ] **Step 1: Run full frontend checks**

```bash
cd frontend
npm run build
npx playwright test e2e/questionnaire.spec.ts e2e/review.spec.ts
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

No code changes remain; update TESTPLAN.md traceability matrix if applicable.

---

## Self-Review

1. **Spec coverage:** The request was "stepped questionnaire". Task 1 converts the page to one-question-per-step with progress and navigation. Task 2 ensures save/resume compatibility. Task 3 verifies everything.
2. **Placeholder scan:** No TBD/TODO. Each step contains code/commands.
3. **Type consistency:** Uses existing `Progress`/`Question`/`Answer`/`FollowUp` types. No new API shapes.
4. **E2E compatibility:** All existing `data-*` selectors are kept. New stepper elements use `data-testid`. The first question remains on step 0, so QSTN-05 selectors still match.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-15-pr-c-questionnaire-questions.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
