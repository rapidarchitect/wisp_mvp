"""Seed the demo tenant and test users for Playwright e2e tests."""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to path so we can import app modules.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ai.fakes import FakeLLM  # noqa: E402

_FAKE_QUESTIONS_JSON = (
    '{"questions": ['
    '{"text": "Do you restrict physical access to servers?"},'
    '{"text": "Do you encrypt laptops?"},'
    '{"text": "Do you perform background checks?"},'
    '{"text": "Do you have an incident response plan?"},'
    '{"text": "Do you review access logs regularly?"},'
    '{"text": "Do you disable accounts on termination?"}'
    ']}'
)
from app.db.control import init_control_db  # noqa: E402
from app.db.tenant import get_tenant_db  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.provisioning import provision_tenant  # noqa: E402
from app.services.seeding import seed_all_domains  # noqa: E402

DATA_DIR = ROOT / "data"
CONTROL_DB = DATA_DIR / "control.db"

TEST_USERS = [
    ("admin@demo.example.com", ["admin"]),
    ("contributor@demo.example.com", ["contributor"]),
    ("reviewer@demo.example.com", ["reviewer"]),
    ("contributor2@demo.example.com", ["contributor"]),
    ("reviewer2@demo.example.com", ["reviewer"]),
]

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # Fixed secret for deterministic tests.


async def _seed_demo_tenant() -> None:
    """Create demo tenant and seed its domains."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    await init_control_db(CONTROL_DB)

    import aiosqlite

    async with aiosqlite.connect(CONTROL_DB) as control_db:
        async with control_db.execute("SELECT id FROM tenants WHERE slug = ?", ("demo",)) as cursor:
            row = await cursor.fetchone()

        if row is not None:
            tenant_id = row[0]
        else:
            cursor = await control_db.execute(
                """
                INSERT INTO tenants (slug, company_name, address, status)
                VALUES (?, ?, ?, ?)
                """,
                ("demo", "Demo Accounting Firm", "1 Demo Way", "active"),
            )
            tenant_id = cursor.lastrowid
            await control_db.commit()

        await provision_tenant(
            control_db,
            tenant_id=tenant_id,
            slug="demo",
            data_dir=DATA_DIR,
        )

        tenant_db = await get_tenant_db(DATA_DIR, "demo")
        try:
            version = await tenant_db.fetchone("SELECT id FROM wisp_versions WHERE number = 1")
            version_id = version["id"]
            await seed_all_domains(
                tenant_db, version_id=version_id, llm=FakeLLM(default=_FAKE_QUESTIONS_JSON)
            )
            await tenant_db.commit()
        finally:
            await tenant_db.close()


def _insert_test_users() -> None:
    """Insert deterministic test users into the demo tenant DB."""
    tenant_db_path = DATA_DIR / "tenants" / "demo.db"
    conn = sqlite3.connect(tenant_db_path)
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


async def main() -> int:
    await _seed_demo_tenant()
    _insert_test_users()
    print(f"E2E_TOTP_SECRET={TOTP_SECRET}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
