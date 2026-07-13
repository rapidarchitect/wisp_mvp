"""Control-plane database connection and initialization."""

import importlib.resources as pkg_resources
from pathlib import Path

import aiosqlite


async def get_control_db(path: str | Path) -> aiosqlite.Connection:
    """Return an aiosqlite connection to the control-plane database.

    The caller is responsible for closing the connection.
    """
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_control_db(path: str | Path) -> aiosqlite.Connection:
    """Create the control-plane DB file and run the schema if it does not exist."""
    conn = await get_control_db(path)
    schema = pkg_resources.files("app.db.schema").joinpath("control.sql").read_text()
    await conn.executescript(schema)
    await conn.commit()
    return conn


async def close_connection(conn: aiosqlite.Connection, timeout: float = 2.0) -> None:
    """Close an aiosqlite connection and wait for its background thread to exit.

    Workaround for aiosqlite issue where close() may return before the
    background thread has fully stopped.
    """
    await conn.close()
    conn.join(timeout=timeout)


async def fetchone(conn: aiosqlite.Connection, sql: str, parameters: tuple | list | dict = ()):
    """Fetch one row from the control DB."""
    async with await conn.execute(sql, parameters) as cursor:
        return await cursor.fetchone()


async def fetchall(conn: aiosqlite.Connection, sql: str, parameters: tuple | list | dict = ()):
    """Fetch all rows from the control DB."""
    async with await conn.execute(sql, parameters) as cursor:
        return await cursor.fetchall()
