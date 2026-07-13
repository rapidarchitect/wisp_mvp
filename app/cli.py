"""WISPGen CLI entry points."""

import argparse
import asyncio
import sys
from pathlib import Path

from app.config import settings
from app.db.control import fetchone, get_control_db, init_control_db
from app.services.provisioning import provision_tenant
from app.services.seeding import seed_all_domains


async def seed_demo(*, data_dir: str | None = None, llm=None) -> dict:
    """Create the demo tenant, provision it, and seed all 14 domains."""
    base = Path(data_dir or settings.data_dir)
    control_db_path = base / "control.db"
    await init_control_db(control_db_path)

    control_db = await get_control_db(control_db_path)
    try:
        existing = await fetchone(
            control_db,
            "SELECT id FROM tenants WHERE slug = ?",
            ("demo",),
        )
        if existing is not None:
            tenant_id = existing["id"]
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
            data_dir=base,
        )

        from app.db.tenant import get_tenant_db

        tenant_db = await get_tenant_db(base, "demo")
        try:
            version = await tenant_db.fetchone("SELECT id FROM wisp_versions WHERE number = 1")
            version_id = version["id"]
            result = await seed_all_domains(tenant_db, version_id=version_id, llm=llm)
            await tenant_db.commit()
        finally:
            await tenant_db.close()
    finally:
        await control_db.close()

    return result


def _run_async(coro):
    """Run an async function from the synchronous CLI."""
    return asyncio.run(coro)


def main(argv: list[str] | None = None) -> int:
    """Run the WISPGen CLI."""
    parser = argparse.ArgumentParser(prog="wispgen")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed-demo", help="Seed the demo tenant")
    seed_parser.set_defaults(func=lambda _args: _run_async(seed_demo()))

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
