"""Unit tests for the follow-up generation crew."""

import pytest

from app.ai.fakes import FakeLLM
from app.crews.followup_crew import FollowUpCrew


def test_generates_followups():
    response = "1. What is the policy number?\n2. Who approved it?\n3. When was it last reviewed?"
    llm = FakeLLM(default=response)
    crew = FollowUpCrew(
        None,
        answer_id=1,
        domain_code="HR",
        domain_name="HR",
        answer_value="yes",
        answer_text="We have a policy.",
        llm=llm,
    )
    result = crew._parse(response)
    assert result == [
        "What is the policy number?",
        "Who approved it?",
        "When was it last reviewed?",
    ]


async def test_generate_truncates_to_three():
    llm = FakeLLM(default="1. A\n2. B\n3. C\n4. D\n5. E")
    crew = FollowUpCrew(
        None,
        answer_id=1,
        domain_code="HR",
        domain_name="HR",
        answer_value="yes",
        answer_text="We have a policy.",
        llm=llm,
    )
    result = await crew.generate()
    assert len(result) == 3


async def test_failure_raises_after_retry():
    llm = FakeLLM(fail=True)
    crew = FollowUpCrew(
        None,
        answer_id=1,
        domain_code="HR",
        domain_name="HR",
        answer_value="yes",
        answer_text="We have a policy.",
        llm=llm,
    )
    with pytest.raises(RuntimeError, match="FakeLLM failure"):
        await crew.generate()
