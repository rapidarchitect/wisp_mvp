"""Unit tests for PDF export service."""

from __future__ import annotations

import io

import pytest
from pdfminer.high_level import extract_text

from app.db.tenant import init_tenant_db
from app.exceptions import NotFoundError
from app.services.pdf import render_wisp_pdf


async def _seed_version(db, *, with_compiled: bool = False):
    await db.execute(
        "INSERT INTO wisp_versions (tenant_id, number, status) VALUES (?, ?, ?)",
        (1, 1, "in_progress"),
    )
    version_id = (await db.fetchone("SELECT id FROM wisp_versions"))["id"]
    await db.execute(
        "INSERT INTO domains (code, name, wisp_version_id, status) VALUES (?, ?, ?, ?)",
        ("AC", "Access Control", version_id, "approved"),
    )
    domain_id = (await db.fetchone("SELECT id FROM domains"))["id"]
    if with_compiled:
        await db.execute(
            """
            INSERT INTO compiled_answers (domain_id, narrative_text, compiled_at)
            VALUES (?, ?, ?)
            """,
            (domain_id, "Compiled narrative text.", "2026-01-01T00:00:00"),
        )
    await db.commit()
    return version_id


@pytest.mark.asyncio
async def test_render_pdf_includes_draft_watermark(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        version_id = await _seed_version(db, with_compiled=True)
        pdf_bytes = await render_wisp_pdf(db, version_id)
    finally:
        await db.close()

    text = extract_text(io.BytesIO(pdf_bytes))
    assert "DRAFT" in text


@pytest.mark.asyncio
async def test_render_pdf_complete_version_excludes_draft(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        version_id = await _seed_version(db, with_compiled=True)
        await db.execute("UPDATE wisp_versions SET status = 'complete' WHERE id = ?", (version_id,))
        await db.commit()
        pdf_bytes = await render_wisp_pdf(db, version_id, include_draft=False)
    finally:
        await db.close()

    text = extract_text(io.BytesIO(pdf_bytes))
    assert "DRAFT" not in text


@pytest.mark.asyncio
async def test_render_pdf_unknown_version_raises(tmp_path):
    db = await init_tenant_db(str(tmp_path), "palmetto")
    try:
        with pytest.raises(NotFoundError):
            await render_wisp_pdf(db, 999)
    finally:
        await db.close()
