"""Step definitions for wisp-versioning-and-export.feature."""

from __future__ import annotations

import io
import sqlite3

from pdfminer.high_level import extract_text
from pytest_bdd import given, parsers, scenario, then, when

from tests.steps.helpers import _tenant_db_path


@scenario(
    "../../features/wisp-versioning-and-export.feature",
    "VERS-01 Draft export carries DRAFT watermark",
)
def test_vers01_draft_export_carries_draft_watermark():
    pass


@scenario(
    "../../features/wisp-versioning-and-export.feature",
    "VERS-02 Complete WISP exports clean",
)
def test_vers02_complete_wisp_exports_clean():
    pass


@scenario(
    "../../features/wisp-versioning-and-export.feature",
    "VERS-03 New version clones approved baseline",
)
def test_vers03_new_version_clones_approved_baseline():
    pass


@scenario(
    "../../features/wisp-versioning-and-export.feature",
    "VERS-04 Only one version in progress",
)
def test_vers04_only_one_version_in_progress():
    pass


@scenario(
    "../../features/wisp-versioning-and-export.feature",
    "VERS-05 Prior versions remain exportable",
)
def test_vers05_prior_versions_remain_exportable():
    pass


@given(parsers.parse('the WISP version status is "{status}"'))
@when(parsers.parse('the WISP version status is "{status}"'))
def given_wisp_version_status(client, context, data_dir, provisioned_tenant, status):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        if status == "complete":
            conn.execute(
                "UPDATE wisp_versions SET status = ?, completed_at = ?",
                (status, "2026-01-01T00:00:00"),
            )
        else:
            conn.execute("UPDATE wisp_versions SET status = ?, completed_at = NULL", (status,))
        conn.commit()
    finally:
        conn.close()


@when("the admin exports the current version")
def when_admin_exports_current_version(client, context):
    response = client.get(
        "/versions/current/export",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    context["export_response"] = response


@when(parsers.parse("the admin exports version {number:d}"))
def when_admin_exports_version(client, context, number):
    response = client.get(
        f"/versions/{number}/export",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    context["export_response"] = response


@given("the admin starts a new version")
@when("the admin starts a new version")
def when_admin_starts_new_version(client, context):
    response = client.post(
        "/versions",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["version_response"] = response.json()


@when("the admin starts a second version")
def when_admin_starts_second_version(client, context):
    response = client.post(
        "/versions",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    context["version_response"] = response


@then("the export response is a PDF")
def then_export_response_is_pdf(context):
    response = context["export_response"]
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    context["pdf_bytes"] = response.content
    context["pdf_text"] = extract_text(io.BytesIO(response.content))


@then(parsers.parse('the PDF contains "{text}"'))
def then_pdf_contains(context, text):
    assert text in context["pdf_text"]


@then(parsers.parse('the PDF does not contain "{text}"'))
def then_pdf_does_not_contain(context, text):
    assert text not in context["pdf_text"]


@then("a second WISP version exists")
def then_second_wisp_version_exists(client, context, data_dir, provisioned_tenant):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM wisp_versions")
        assert cur.fetchone()[0] == 2
    finally:
        conn.close()


@then(parsers.parse('the new version status is "{status}"'))
def then_new_version_status(client, context, data_dir, provisioned_tenant, status):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT status FROM wisp_versions ORDER BY number DESC LIMIT 1")
        assert cur.fetchone()[0] == status
    finally:
        conn.close()


@then(parsers.parse('domain "{code}" in the new version has a compiled answer'))
def then_domain_in_new_version_has_compiled_answer(
    client, context, data_dir, provisioned_tenant, code
):
    path = _tenant_db_path(data_dir, provisioned_tenant)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM compiled_answers ca
            JOIN domains d ON d.id = ca.domain_id
            JOIN wisp_versions v ON v.id = d.wisp_version_id
            WHERE d.code = ? AND v.number = (SELECT MAX(number) FROM wisp_versions)
            """,
            (code,),
        )
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()


@then(parsers.parse('the request is rejected with "{code}"'))
def then_request_rejected_with_code(context, code):
    response = context["version_response"]
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == code
