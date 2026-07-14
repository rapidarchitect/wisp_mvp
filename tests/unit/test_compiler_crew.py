"""Unit tests for CompilerCrew."""

from __future__ import annotations

import pytest

from app.ai.fakes import FakeLLM
from app.crews.compiler_crew import CompilerCrew


@pytest.mark.asyncio
async def test_compiler_crew_returns_narrative():
    crew = CompilerCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        conversation=[
            {
                "question": "Do you restrict physical access?",
                "answer": "yes",
                "followups": [
                    {
                        "text": "How do you badge visitors?",
                        "response": "front desk issues temporary badges",
                    }
                ],
            }
        ],
        llm=FakeLLM(default="We restrict physical access and badge visitors at the front desk."),
    )
    result = await crew.compile()
    assert isinstance(result, str)
    assert "badge" in result.lower()


@pytest.mark.asyncio
async def test_compiler_crew_retries_on_failure():
    calls = []

    class FlakyLLM(FakeLLM):
        def call(self, messages, tools=None, callbacks=None, available_functions=None):
            calls.append(messages)
            if len(calls) < 2:
                raise RuntimeError("flaky")
            return "Recovered narrative."

    crew = CompilerCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        conversation=[],
        llm=FlakyLLM(),
    )
    result = await crew.compile()
    assert result == "Recovered narrative."
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_compiler_crew_raises_after_exhausted_retries():
    crew = CompilerCrew(
        None,
        domain_code="AC",
        domain_name="Access Control",
        conversation=[],
        llm=FakeLLM(fail=True),
    )
    with pytest.raises(RuntimeError):
        await crew.compile()
