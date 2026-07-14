"""Unit tests for RevisionCrew."""

from __future__ import annotations

import pytest

from app.ai.fakes import FakeLLM
from app.crews.revision_crew import RevisionCrew


@pytest.mark.asyncio
async def test_revision_crew_returns_revised_narrative():
    crew = RevisionCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        current_narrative="We lock the doors.",
        conversation=[],
        llm=FakeLLM(default="We lock the doors and badge visitors."),
    )
    result = await crew.revise("Add detail about visitor badges")
    assert isinstance(result, str)
    assert "badge" in result.lower()


@pytest.mark.asyncio
async def test_revision_crew_retries_on_failure():
    calls = []

    class FlakyLLM(FakeLLM):
        def call(self, messages, tools=None, callbacks=None, available_functions=None):
            calls.append(messages)
            if len(calls) < 2:
                raise RuntimeError("flaky")
            return "Revised narrative."

    crew = RevisionCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        current_narrative="x",
        conversation=[],
        llm=FlakyLLM(),
    )
    result = await crew.revise("make it better")
    assert result == "Revised narrative."
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_revision_crew_raises_after_exhausted_retries():
    crew = RevisionCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        current_narrative="x",
        conversation=[],
        llm=FakeLLM(fail=True),
    )
    with pytest.raises(RuntimeError):
        await crew.revise("make it better")
