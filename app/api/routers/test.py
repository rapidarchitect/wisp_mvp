"""Test-only endpoints for frontend E2E support. Disabled outside test mode."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.middleware.tenancy import get_tenant_db_from_request
from app.services.auth import hash_password
from app.services.email_backends import clear_sent_messages, get_sent_messages
from app.services.payment import FakeStripeClient

router = APIRouter()


def _require_test_mode():
    if not settings.enable_test_endpoints:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/invitations")
async def list_invitations(request: Request, email: str | None = None) -> list[dict]:
    """Return invitations so E2E tests can extract activation tokens."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    if email:
        rows = await db.fetchall(
            "SELECT email, roles, token, expires_at, accepted_at FROM invitations WHERE email = ?",
            (email,),
        )
    else:
        rows = await db.fetchall(
            """
            SELECT email, roles, token, expires_at, accepted_at
            FROM invitations
            ORDER BY id DESC LIMIT 10
            """
        )
    return [dict(row) for row in rows]


@router.post("/users")
async def create_test_user(request: Request, payload: dict) -> dict:
    """Create a user directly for E2E seeding."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    await db.execute(
        """
        INSERT INTO users (
            email, password_hash, roles, status, totp_secret, totp_enrolled, failed_attempts
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["email"],
            hash_password(payload["password"]),
            payload.get("roles", '["contributor"]'),
            payload.get("status", "active"),
            payload.get("totp_secret"),
            1 if payload.get("totp_enrolled", True) else 0,
            0,
        ),
    )
    await db.commit()
    return {"created": True}


@router.post("/reset-domain/{code}")
async def reset_domain(request: Request, code: str) -> dict:
    """Reset a single domain to assigned status and delete its answers."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    row = await db.fetchone("SELECT id FROM domains WHERE code = ?", (code,))
    if not row:
        raise HTTPException(status_code=404, detail="domain not found")
    domain_id = row["id"]
    await db.execute(
        "DELETE FROM answers WHERE question_id IN (SELECT id FROM questions WHERE domain_id = ?)",
        (domain_id,),
    )
    await db.execute("DELETE FROM compiled_answers WHERE domain_id = ?", (domain_id,))
    await db.execute(
        "UPDATE domains SET status = 'assigned' WHERE id = ?",
        (domain_id,),
    )
    await db.execute(
        "UPDATE wisp_versions SET status = 'in_progress', completed_at = NULL "
        "WHERE id = (SELECT wisp_version_id FROM domains WHERE id = ?)",
        (domain_id,),
    )
    await db.commit()
    return {"reset": True}


@router.post("/login")
async def test_login(request: Request, payload: dict) -> dict:
    """Test-only login that bypasses TOTP to avoid clock-drift flakes in E2E helpers."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    user = await db.fetchone(
        "SELECT id, email, roles, status FROM users WHERE email = ?",
        (payload["email"],),
    )
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    from app.services.auth import create_session

    token = await create_session(db, user["id"])
    return {"token": token, "user": dict(user)}


@router.post("/reset-all")
async def reset_all(request: Request) -> dict:
    """Reset the entire demo tenant to a known E2E baseline."""
    _require_test_mode()
    # Reset global service doubles to their default modes so one test's failure
    # mode does not leak into the next test.
    request.app.state.stripe_client = FakeStripeClient("succeed")
    request.app.state.llm = None
    db = get_tenant_db_from_request(request)

    # Reset the demo voucher in the control DB so voucher-signup E2E tests can
    # redeem it repeatedly. SQLite access is sync; this is test-only code.
    import sqlite3
    from pathlib import Path

    control_conn = sqlite3.connect(str(Path(settings.data_dir) / "control.db"))
    try:
        control_conn.execute(
            "UPDATE vouchers SET redeemed_by_tenant_id = NULL, redeemed_at = NULL WHERE code = ?",
            ("WISP-2026-DEMO",),
        )
        control_conn.commit()
    finally:
        control_conn.close()

    async def _do_reset():
        await db.execute("BEGIN IMMEDIATE")
        try:
            # Wipe volatile domain/version state and rebuild a single in-progress
            # version with 14 empty domains. This prevents prior `versions.spec.ts`
            # runs from leaving extra versions that break domain-assignment tests.
            await db.execute("DELETE FROM followups")
            await db.execute("DELETE FROM answers")
            await db.execute("DELETE FROM compiled_answers")
            await db.execute("DELETE FROM domain_assignments")
            await db.execute("DELETE FROM questions")
            await db.execute("DELETE FROM domains")
            await db.execute("DELETE FROM wisp_versions")
            await db.execute(
                "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
                (1, 1, "in_progress"),
            )
            version_row = await db.fetchone("SELECT id FROM wisp_versions WHERE number = 1")
            version_id = version_row["id"]
            from app.services.provisioning import _DOMAINS

            await db.executemany(
                "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
                [(code, name, version_id, "pending_questions") for code, name in _DOMAINS],
            )
            # Seed deterministic questions for each domain.
            seeded_questions = [
                "Do you restrict physical access to servers?",
                "Do you encrypt laptops?",
                "Do you perform background checks?",
                "Do you have an incident response plan?",
                "Do you review access logs regularly?",
                "Do you disable accounts on termination?",
            ]
            domains = await db.fetchall(
                "SELECT id FROM domains WHERE wisp_version_id = ?", (version_id,)
            )
            for domain_row in domains:
                for position, text in enumerate(seeded_questions, start=1):
                    await db.execute(
                        """
                        INSERT INTO questions (domain_id, text, answer_type, origin, position)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (domain_row["id"], text, "yes_no", "seeded", position),
                    )

            # Clear any lockout/failed-attempt state so tests start with clean auth.
            await db.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL")
            # Remove ad-hoc test users created during E2E runs.
            await db.execute("DELETE FROM users WHERE email LIKE 'e2e%@demo.example.com'")

            contributor = await db.fetchone(
                "SELECT id FROM users WHERE email = ?", ("contributor@demo.example.com",)
            )
            reviewer = await db.fetchone(
                "SELECT id FROM users WHERE email = ?", ("reviewer@demo.example.com",)
            )
            domain = await db.fetchone(
                "SELECT id FROM domains WHERE code = ? AND wisp_version_id = ?", ("AC", version_id)
            )
            if contributor and reviewer and domain:
                await db.execute(
                    """
                    INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(domain_id) DO UPDATE SET
                        contributor_id = excluded.contributor_id,
                        reviewer_id = excluded.reviewer_id
                    """,
                    (domain["id"], contributor["id"], reviewer["id"]),
                )
                await db.execute(
                    "UPDATE domains SET status = ? WHERE id = ?",
                    ("assigned", domain["id"]),
                )
            await db.commit()
        except Exception:
            await db.execute("ROLLBACK")
            raise

    import asyncio
    from sqlite3 import OperationalError

    for attempt in range(10):
        try:
            await _do_reset()
            break
        except OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < 9:
                await asyncio.sleep(0.05 * (attempt + 1))
                continue
            raise

    # Clear captured console emails so each E2E test gets its own messages.
    clear_sent_messages()

    return {"reset": True}


@router.get("/domains")
async def list_all_domains(request: Request) -> list[dict]:
    """Return all domain codes in the current tenant version for E2E helpers."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    rows = await db.fetchall(
        """
        SELECT d.id, d.code, d.status
        FROM domains d
        WHERE d.wisp_version_id = (SELECT id FROM wisp_versions ORDER BY number DESC LIMIT 1)
        ORDER BY d.code
        """
    )
    return [dict(row) for row in rows]


@router.post("/stripe-mode")
async def set_stripe_mode(request: Request, payload: dict) -> dict:
    """Toggle the fake Stripe client between succeed and decline modes."""
    _require_test_mode()
    mode = payload.get("mode", "succeed")
    if mode not in ("succeed", "decline"):
        raise HTTPException(status_code=400, detail="invalid_mode")
    request.app.state.stripe_client = FakeStripeClient(mode=mode)
    return {"mode": mode}


@router.post("/llm-mode")
async def set_llm_mode(request: Request, payload: dict) -> dict:
    """Toggle the fake LLM between normal and failure modes."""
    _require_test_mode()
    from app.ai.fakes import FakeLLM

    mode = payload.get("mode", "normal")
    if mode not in ("normal", "fail"):
        raise HTTPException(status_code=400, detail="invalid_mode")
    request.app.state.llm = FakeLLM(fail=mode == "fail")
    return {"mode": mode}


@router.get("/sent-emails")
async def list_sent_emails(request: Request, email: str | None = None) -> list[dict]:
    """Return console emails captured by the email backend.

    E2E tests use this to extract password-reset links and invitation tokens
    without a real mailbox.
    """
    _require_test_mode()
    messages = get_sent_messages()
    if email:
        return [m for m in messages if m.get("to") == email]
    return messages


@router.post("/expire-invitation")
async def expire_invitation(request: Request, payload: dict) -> dict:
    """Make the newest pending invitation for an email expire."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    email = payload["email"]
    row = await db.fetchone(
        """
        SELECT id FROM invitations
        WHERE email = ? AND accepted_at IS NULL
        ORDER BY id DESC LIMIT 1
        """,
        (email,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="invitation not found")
    await db.execute(
        "UPDATE invitations SET expires_at = ? WHERE id = ?",
        ((datetime.now(UTC) - timedelta(hours=1)).isoformat(), row["id"]),
    )
    await db.commit()
    return {"expired": True}


@router.get("/domain-answers/{code}")
async def list_domain_answers(request: Request, code: str) -> list[dict]:
    """Return answers for a domain (for verifying USER-06 preservation)."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    domain = await db.fetchone("SELECT id FROM domains WHERE code = ?", (code,))
    if domain is None:
        raise HTTPException(status_code=404, detail="domain not found")
    rows = await db.fetchall(
        """
        SELECT a.id, a.value, a.skipped, q.position
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        WHERE q.domain_id = ?
        ORDER BY q.position
        """,
        (domain["id"],),
    )
    return [dict(row) for row in rows]


@router.post("/expire-sessions")
async def expire_sessions(request: Request, payload: dict) -> dict:
    """Delete all sessions for a user to simulate session expiry."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    email = payload["email"]
    user = await db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    await db.commit()
    return {"expired": True}


@router.get("/questions/{code}")
async def list_domain_questions(request: Request, code: str) -> list[dict]:
    """Return all questions for a domain."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    domain = await db.fetchone("SELECT id FROM domains WHERE code = ?", (code,))
    if domain is None:
        raise HTTPException(status_code=404, detail="domain not found")
    rows = await db.fetchall(
        """
        SELECT id, text, origin, enabled, position
        FROM questions
        WHERE domain_id = ? ORDER BY position
        """,
        (domain["id"],),
    )
    return [dict(row) for row in rows]


@router.post("/seed-domain/{code}")
async def seed_domain(request: Request, code: str, payload: dict | None = None) -> dict:
    """Re-seed a single domain with fresh questions and set status to seeded."""
    _require_test_mode()
    db = get_tenant_db_from_request(request)
    domain = await db.fetchone("SELECT id, wisp_version_id FROM domains WHERE code = ?", (code,))
    if domain is None:
        raise HTTPException(status_code=404, detail="domain not found")
    # Delete old questions and answers so the seeder can run cleanly.
    old_questions = await db.fetchall(
        "SELECT id FROM questions WHERE domain_id = ?",
        (domain["id"],),
    )
    old_question_ids = tuple(q["id"] for q in old_questions)
    if old_question_ids:
        placeholders = ",".join("?" for _ in old_question_ids)
        answer_ids = await db.fetchall(
            f"SELECT id FROM answers WHERE question_id IN ({placeholders})",
            old_question_ids,
        )
        answer_id_values = tuple(a["id"] for a in answer_ids)
        if answer_id_values:
            a_placeholders = ",".join("?" for _ in answer_id_values)
            await db.execute(
                f"DELETE FROM followups WHERE answer_id IN ({a_placeholders})",
                answer_id_values,
            )
        await db.execute(
            f"DELETE FROM answers WHERE question_id IN ({placeholders})",
            old_question_ids,
        )
    await db.execute("DELETE FROM questions WHERE domain_id = ?", (domain["id"],))
    await db.execute(
        "UPDATE domains SET status = 'pending_questions' WHERE id = ?",
        (domain["id"],),
    )
    await db.commit()

    from app.ai.fakes import FakeLLM
    from app.services.seeding import retry_domain_seed

    body = payload or {}
    llm = FakeLLM(fail=True) if body.get("fail") else None
    result = await retry_domain_seed(db, domain_id=domain["id"], llm=llm)
    return result
