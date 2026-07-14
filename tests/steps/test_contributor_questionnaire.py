"""Step definitions for contributor-questionnaire.feature."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from app.ai.fakes import FakeLLM


@pytest.fixture(autouse=True)
def _fake_followup_llm(monkeypatch):
    """Return deterministic follow-ups for questionnaire scenarios."""
    monkeypatch.setattr(
        "app.crews.followup_crew.create_llm",
        lambda _provider=None: FakeLLM(default="1. Why?\n2. How?"),
    )


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-01 Answering a question generates up to 3 follow-ups",
)
def test_qstn01_answer_generates_followups():
    pass


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-04 Skipped questions block submission",
)
def test_qstn04_skipped_blocks_submission():
    pass


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-05 Contributor saves progress and resumes",
)
def test_qstn05_save_and_resume_progress():
    pass


@scenario(
    "../../features/contributor-questionnaire.feature",
    "QSTN-06 AI outage waives follow-ups gracefully",
)
def test_qstn06_ai_outage_waives_followups():
    pass


@given(parsers.parse('a seeded question "{text}" in domain "{code}"'))
def given_seeded_question(client, context, text, code):
    """Seed a single question in the given domain and store its id."""
    import sqlite3

    data_dir = client.app.state.data_dir
    path = data_dir / "tenants" / "palmetto.db"
    conn = sqlite3.connect(path)
    try:
        domain_id = conn.execute("SELECT id FROM domains WHERE code = ?", (code,)).fetchone()[0]
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM questions WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()[0]
        cur = conn.execute(
            """
            INSERT INTO questions (domain_id, text, answer_type, origin, enabled, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (domain_id, text, "yes_no", "seeded", 1, max_pos + 1),
        )
        conn.commit()
        context["question_id"] = cur.lastrowid
    finally:
        conn.close()


@given(parsers.parse("the follow-up LLM is configured to fail"))
def given_followup_llm_fails(monkeypatch):
    """Make follow-up generation raise on every call."""
    monkeypatch.setattr(
        "app.crews.followup_crew.create_llm", lambda _provider=None: FakeLLM(fail=True)
    )


@when(parsers.parse('"{email}" answers "{value}" to the question'))
def when_contributor_answers_question(client, context, email, value):
    """POST an answer to the seeded question."""
    response = client.post(
        f"/questions/{context['question_id']}/answer",
        json={"value": value},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["answer_response"] = response.json()


@when(parsers.parse('"{email}" skips the question'))
def when_contributor_skips_question(client, context, email):
    """POST a skipped answer for the seeded question."""
    response = client.post(
        f"/questions/{context['question_id']}/answer",
        json={"skipped": True},
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    context["answer_response"] = response.json()


@when(parsers.parse('"{email}" signs out'))
def when_contributor_signs_out(context, email):
    """Clear the session token so a subsequent sign-in is required."""
    context.pop("session_token", None)


@then("the response contains between 1 and 3 follow-up questions")
def then_response_contains_followups(context):
    followups = context["answer_response"]["followups"]
    assert 1 <= len(followups) <= 3


@then(parsers.parse('the domain "{code}" progress shows submit_ready false'))
def then_domain_progress_not_submit_ready(client, context, code):
    response = client.get(
        f"/domains/{code}/progress",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["submit_ready"] is False


@then(parsers.parse('the domain "{code}" progress shows submit_ready true'))
def then_domain_progress_submit_ready(client, context, code):
    response = client.get(
        f"/domains/{code}/progress",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["submit_ready"] is True


@then(parsers.parse('the domain "{code}" progress shows the same answer and follow-ups'))
def then_domain_progress_preserved(client, context, code):
    response = client.get(
        f"/domains/{code}/progress",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    progress = response.json()
    answered = [q for q in progress["questions"] if q["answer"]][0]
    assert answered["answer"]["value"] == context["answer_response"]["value"]
    assert [f["text"] for f in answered["answer"]["followups"]] == [
        f["text"] for f in context["answer_response"]["followups"]
    ]


@then(parsers.parse('the answer follow-up state is "{state}"'))
def then_answer_followup_state(context, state):
    assert context["answer_response"]["followups_state"] == state


@then(parsers.parse('the contributor receives a "{kind}" notification'))
def then_contributor_notification(client, context, kind):
    response = client.get(
        "/notifications?unread_only=true",
        headers={"Authorization": f"Bearer {context['session_token']}"},
    )
    assert response.status_code == 200
    notifications = response.json()
    assert any(n["type"] == kind for n in notifications)
