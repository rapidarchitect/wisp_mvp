# Session Learnings — WISPGen

## 2026-07-14: FakeLLM default must remain the unit-test contract
- **What**: Changed `FakeLLM.call` to ignore its `default` argument and return prompt-keyed fallback text, breaking unit tests that inject `default="1. Why?"`.
- **Why**: I treated the E2E deterministic output requirement as a reason to override the constructor contract.
- **Rule**: Preserve explicit constructor/default inputs as the highest-priority fallback; add keyword-based fallbacks only when no default is supplied.

## 2026-07-14: E2E login via UI is fragile across long setup sequences
- **What**: `versions.spec.ts` spent 12s approving 14 domains via API, then the admin UI login used a TOTP code from a stale 30s window and failed.
- **Why**: Playwright tests starting from the browser login page are subject to TOTP clock drift and ordering delays.
- **Rule**: For long setup sequences, log in through the API inside the test and seed `localStorage` with the returned JWT before navigating. Share a single `loginAsApi` helper across E2E specs.

## 2026-07-14: `sqlite3.Row` does not have `.get()`
- **What**: `domain.get("reviewer_id")` in `app/services/answers.py` raised `AttributeError` during review progress load.
- **Why**: I assumed row-like objects behave like dicts.
- **Rule**: Convert `sqlite3.Row` to `dict(row)` before using dict-style accessors in services.
