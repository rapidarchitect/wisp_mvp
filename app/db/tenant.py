"""Per-tenant SQLite database factory."""

import importlib.resources as pkg_resources
from pathlib import Path

import aiosqlite


class TenantDB:
    """Wrapper around an aiosqlite connection for a single tenant.

    This is the only object that should be passed to tenant-scoped code.
    It exists to make tenant boundaries explicit (C-01).
    """

    def __init__(self, conn: aiosqlite.Connection, slug: str) -> None:
        self._conn = conn
        self.slug = slug

    async def execute(self, sql: str, parameters: tuple | list | dict = ()):
        """Execute a parameterized query against this tenant's DB."""
        return await self._conn.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: list):
        """Execute a parameterized query many times."""
        return await self._conn.executemany(sql, parameters)

    async def executescript(self, sql: str):
        """Execute a script against this tenant's DB."""
        return await self._conn.executescript(sql)

    async def fetchone(self, sql: str, parameters: tuple | list | dict = ()):
        """Fetch one row."""
        async with await self._conn.execute(sql, parameters) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, parameters: tuple | list | dict = ()):
        """Fetch all rows."""
        async with await self._conn.execute(sql, parameters) as cursor:
            return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._conn.commit()

    async def close(self) -> None:
        """Close the underlying connection and wait for its thread to exit."""
        await self._conn.close()
        self._conn.join(timeout=2.0)


def tenant_db_path(data_dir: str | Path, slug: str) -> Path:
    """Return the filesystem path for a tenant's SQLite file."""
    base = Path(data_dir)
    tenants_dir = base / "tenants"
    tenants_dir.mkdir(parents=True, exist_ok=True)
    return tenants_dir / f"{slug}.db"


async def get_tenant_db(data_dir: str | Path, slug: str) -> TenantDB:
    """Open a connection to a tenant's database.

    The file is created if it does not exist, but the schema is NOT applied.
    Use init_tenant_db for new tenants.
    """
    path = tenant_db_path(data_dir, slug)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA journal_mode=WAL")
    return TenantDB(conn, slug)


async def init_tenant_db(data_dir: str | Path, slug: str) -> TenantDB:
    """Create a tenant's SQLite file and apply the full schema."""
    tenant = await get_tenant_db(data_dir, slug)
    schema = pkg_resources.files("app.db.schema").joinpath("tenant.sql").read_text()
    await tenant.executescript(schema)
    await tenant.commit()
    return tenant
