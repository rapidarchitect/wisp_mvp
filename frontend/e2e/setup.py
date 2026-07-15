"""Seed the demo tenant and test users for Playwright e2e tests."""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.auth import hash_password  # noqa: E402
from app.services.provisioning import _create_initial_version, _insert_empty_domains  # noqa: E402

DATA_DIR = ROOT / "data"
CONTROL_DB = DATA_DIR / "control.db"
TENANT_DB = DATA_DIR / "tenants" / "demo.db"

TEST_USERS = [
    ("admin@demo.example.com", ["admin"]),
    ("contributor@demo.example.com", ["contributor"]),
    ("reviewer@demo.example.com", ["reviewer"]),
    ("contributor2@demo.example.com", ["contributor"]),
    ("reviewer2@demo.example.com", ["reviewer"]),
]

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # Fixed secret for deterministic tests.


def _init_control_db() -> int:
    """Ensure control DB exists and demo tenant is registered."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema = (ROOT / "app" / "db" / "schema" / "control.sql").read_text()
    conn = sqlite3.connect(CONTROL_DB)
    try:
        conn.executescript(schema)
        conn.commit()
        existing = conn.execute("SELECT id FROM tenants WHERE slug = ?", ("demo",)).fetchone()
        if existing:
            return existing[0]
        cur = conn.execute(
            "INSERT INTO tenants (slug, company_name, address, status) VALUES (?, ?, ?, ?)",
            ("demo", "Demo Accounting Firm", "1 Demo Way", "active"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _init_tenant_db(tenant_id: int) -> None:
    """Provision the demo tenant DB with schema and 14 empty domains."""
    TENANT_DB.parent.mkdir(parents=True, exist_ok=True)
    schema = (ROOT / "app" / "db" / "schema" / "tenant.sql").read_text()
    conn = sqlite3.connect(TENANT_DB)
    try:
        conn.executescript(schema)
        conn.execute("PRAGMA foreign_keys=ON")
        existing = conn.execute(
            "SELECT id FROM wisp_versions WHERE tenant_id = ? AND number = 1", (tenant_id,)
        ).fetchone()
        if existing is None:
            version_id = _create_initial_version(conn, tenant_id=tenant_id)
            _insert_empty_domains(conn, version_id=version_id)
        # Reset assignment and answer data that E2E tests expect to start fresh.
        conn.execute(
            """
            DELETE FROM followups
            WHERE answer_id IN (SELECT id FROM answers)
            """
        )
        conn.execute("DELETE FROM answers")
        conn.execute("DELETE FROM compiled_answers")
        conn.execute("DELETE FROM domain_assignments")
        conn.execute("UPDATE wisp_versions SET status = 'in_progress', completed_at = NULL")
        conn.execute(
            "UPDATE domains SET status = 'pending_questions' WHERE status != 'pending_questions'"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_questions() -> None:
    """Seed deterministic questions for each domain, idempotently."""
    questions = [
        "Do you restrict physical access to servers?",
        "Do you encrypt laptops?",
        "Do you perform background checks?",
        "Do you have an incident response plan?",
        "Do you review access logs regularly?",
        "Do you disable accounts on termination?",
    ]
    conn = sqlite3.connect(TENANT_DB)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        for domain in conn.execute("SELECT id FROM domains").fetchall():
            domain_id = domain[0]
            existing = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE domain_id = ?", (domain_id,)
            ).fetchone()[0]
            if existing:
                continue
            for position, text in enumerate(questions, start=1):
                conn.execute(
                    """
                    INSERT INTO questions (domain_id, text, answer_type, origin, position)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (domain_id, text, "yes_no", "seeded", position),
                )
        conn.commit()
    finally:
        conn.close()


def _insert_test_users() -> None:
    """Insert deterministic test users into the demo tenant DB."""
    conn = sqlite3.connect(TENANT_DB)
    try:
        for email, roles in TEST_USERS:
            existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            password_hash = hash_password("UserPass123!")
            roles_json = json.dumps(roles)
            if existing:
                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, roles = ?, status = ?, totp_secret = ?, totp_enrolled = ?
                    WHERE id = ?
                    """,
                    (password_hash, roles_json, "active", TOTP_SECRET, 1, existing[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO users (
                        email, password_hash, roles, status,
                        totp_secret, totp_enrolled, failed_attempts
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (email, password_hash, roles_json, "active", TOTP_SECRET, 1, 0),
                )
        conn.commit()
    finally:
        conn.close()


def _seed_assignment() -> None:
    """Assign domain AC to the demo contributor and reviewer."""
    conn = sqlite3.connect(TENANT_DB)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        contributor = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("contributor@demo.example.com",)
        ).fetchone()
        reviewer = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("reviewer@demo.example.com",)
        ).fetchone()
        domain = conn.execute("SELECT id FROM domains WHERE code = ?", ("AC",)).fetchone()
        if contributor and reviewer and domain:
            conn.execute(
                """
                INSERT INTO domain_assignments (domain_id, contributor_id, reviewer_id)
                VALUES (?, ?, ?)
                ON CONFLICT(domain_id) DO UPDATE SET
                    contributor_id = excluded.contributor_id,
                    reviewer_id = excluded.reviewer_id
                """,
                (domain[0], contributor[0], reviewer[0]),
            )
            conn.execute("UPDATE domains SET status = ? WHERE id = ?", ("assigned", domain[0]))
            conn.commit()
    finally:
        conn.close()


def main() -> int:
    tenant_id = _init_control_db()
    _init_tenant_db(tenant_id)
    _seed_questions()
    _insert_test_users()
    _seed_assignment()
    print(f"E2E_TOTP_SECRET={TOTP_SECRET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
