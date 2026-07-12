# OpenCode Bootstrap Prompt — WISPGen

> Paste this prompt into OpenCode to begin development.
> Ensure `AGENTS.md`, `constitution.md`, `SPEC.md`, and `TESTPLAN.md` are in the project root.

---

You are starting a new development session for **WISPGen**, a multi-tenant SaaS that generates Written Information Security Programs for small accounting firms.

## Step 1: Read AGENTS.md

Read `AGENTS.md` first. It contains the compact repo-specific guidance, current repo state, developer commands, and hard rules for this session.

## Step 2: Read the Constitution

Read `constitution.md` in the project root. These are immutable project rules. Do not proceed until you understand the coding standards, testing requirements, agent boundaries (especially the NEVER tier), and the quality gate protocol. You may not modify this file.

## Step 3: Read the Spec and Behavior Set

Read `SPEC.md`. Focus on:
- Section 2 (Non-Goals) — know what you are NOT building
- Section 3 constraints C-01 through C-19 — these are normative and cited in code
- Section 5 (Tech Stack) and Section 6 (Commands) — verify build, test, and lint run
- Section 8 (Task Decomposition) — identify the current task

Then read `TESTPLAN.md` (traceability matrix, step definition layout, TDD loop).

Note: `features/` and `docs/bdd/` are referenced in the specs but do not exist yet. See `docs/bdd/feature-index.md` for the scenario inventory.

## Step 4: Plan the Current Task

Read the task block for the task you are implementing in `SPEC.md` Section 8. Enter PLAN MODE. Your plan must name:
- The directory and file layout you will create or modify
- Which scenarios apply (if any) and which step definitions will be written first
- Which constraints are touched and how you will enforce them

Do not write executable code until the plan is reviewed and approved.

## Step 5: Implement After Approval

For every task, in this order:
1. Write the failing pytest-bdd step definitions for the task's scenario IDs (red for the right reason: missing implementation, not missing glue)
2. Write the failing unit tests beneath them (red)
3. Implement the minimum code to go green — units first, then scenarios
4. Refactor with everything green; run `uv run ruff check . && uv run ruff format --check .`
5. Run the FULL BDD suite (`uv run pytest tests/steps -q`) — the task is not done if any other scenario broke
6. Update the `TESTPLAN.md` matrix status and check the task's acceptance criteria

## Ongoing Rules
- NEVER edit or create `features/*.feature` without explicit human approval — feature files are spec.
- A scenario that fails after previously passing is a stop-the-line event. Halt and report; do not edit the scenario, do not xfail, do not delete.
- Before each new task, re-read only that task's block and its `TESTPLAN.md` rows.
- Never add dependencies beyond the constitution's approved list without asking.
- Tests never call real LLM, Tavily, Stripe, or SES endpoints — doubles only.
- Never open another tenant's database file; tenant identity comes from the resolved subdomain only (C-01).
- Never log tenant answers, vitals, or TOTP secrets (C-18).
- Never skip tests, never force-push, one task per branch (`task-NN-short-desc`), commits cite task and constraint IDs.
- If your implementation deviates from `SPEC.md`, update the spec FIRST (with approval).

Confirm you have read `AGENTS.md`, `constitution.md`, `SPEC.md`, and `TESTPLAN.md`, then present your plan for the current task.
