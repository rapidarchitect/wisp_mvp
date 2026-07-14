"""PDF export service for WISP versions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fpdf import FPDF

from app.db.tenant import TenantDB
from app.exceptions import NotFoundError


class _WispPDF(FPDF):
    """PDF renderer for a WISP version."""

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(
            0,
            10,
            "Written Information Security Program",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _load_vitals(db: TenantDB) -> dict[str, Any]:  # noqa: ARG001
    """Load company vitals from the tenant DB.

    Placeholder implementation: corporate_vitals currently stores operational
    fields, not address/contact. Callers may pass an explicit company_name to
    render_wisp_pdf. A future schema update can store address/contact here.
    """
    return {
        "company_name": "",
        "address_line1": "",
        "address_city": "",
        "address_state": "",
        "address_zip": "",
        "contact_email": "",
        "contact_phone": "",
    }


async def render_wisp_pdf(
    db: TenantDB,
    version_id: int,
    *,
    company_name: str = "",
    include_draft: bool = True,
) -> bytes:
    """Render a WISP version as a PDF byte stream.

    The DRAFT watermark is included unless the version is complete (C-13).
    """
    version = await db.fetchone(
        "SELECT id, number, status FROM wisp_versions WHERE id = ?", (version_id,)
    )
    if version is None:
        raise NotFoundError(f"version {version_id} not found")

    vitals = _load_vitals(db)
    display_company = company_name or vitals.get("company_name") or "[Company Name]"
    domains = await db.fetchall(
        """
        SELECT d.code, d.name, c.narrative_text
        FROM domains d
        LEFT JOIN compiled_answers c ON c.domain_id = d.id
        WHERE d.wisp_version_id = ?
        ORDER BY d.id
        """,
        (version_id,),
    )

    pdf = _WispPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, display_company, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Written Information Security Program", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    address_parts = [
        vitals.get("address_line1", ""),
        " ".join(
            p
            for p in [
                vitals.get("address_city", ""),
                vitals.get("address_state", ""),
                vitals.get("address_zip", ""),
            ]
            if p
        ),
    ]
    for part in address_parts:
        if part:
            pdf.cell(0, 5, part, new_x="LMARGIN", new_y="NEXT")
    if vitals.get("contact_email"):
        pdf.cell(0, 5, vitals["contact_email"], new_x="LMARGIN", new_y="NEXT")
    if vitals.get("contact_phone"):
        pdf.cell(0, 5, vitals["contact_phone"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    if include_draft:
        pdf.set_font("Helvetica", "B", 48)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 30, "DRAFT", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Security Domains", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for domain in domains:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"{domain['code']} - {domain['name']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        narrative = domain["narrative_text"] or "[No approved narrative for this domain]"
        pdf.multi_cell(0, 5, narrative)
        pdf.ln(4)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 6, f"Generated: {generated_at}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
