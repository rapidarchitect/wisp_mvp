"""Shared helpers for pytest-bdd step definitions."""

from pathlib import Path


def _tenant_db_path(data_dir: Path, slug: str) -> Path:
    return data_dir / "tenants" / f"{slug}.db"
