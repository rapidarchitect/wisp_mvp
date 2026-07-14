"""CrewAI crew that generates follow-up questions from a contributor answer."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


class FollowUpCrew(CrewBase):
    """Generate up to 3 short follow-up questions from a single answer."""

    def __init__(
        self,
        db: TenantDB | None,
        *,
        answer_id: int,
        domain_code: str,
        domain_name: str,
        answer_value: str,
        answer_text: str | None = None,
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.answer_id = answer_id
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.answer_value = answer_value
        self.answer_text = answer_text or ""
        self.llm = llm or create_llm()

    async def generate(self) -> list[str]:
        """Return a list of follow-up texts, retrying once on failure."""
        return await self.run_with_retry(self._generate_once, max_retries=1)

    async def _generate_once(self) -> list[str]:
        prompt = self._build_prompt()
        raw = await self._call_llm(prompt)
        return self._parse(raw)

    def _build_prompt(self) -> str:
        return (
            "You are a security compliance analyst writing a "
            "Written Information Security Program.\n"
            f"Domain: {self.domain_name} ({self.domain_code})\n"
            f"The contributor answered a yes/no question with value '{self.answer_value}'.\n"
            f"Additional context: {self.answer_text}\n"
            "Generate up to 3 short, specific follow-up questions that dig deeper into the answer. "
            "Number each question. Return only the numbered list."
        )

    async def _call_llm(self, prompt: str) -> str:
        """Invoke the LLM and return the response text."""
        result = self.llm.call(prompt)
        if isinstance(result, str):
            return result
        raise RuntimeError("LLM did not return a string response")

    def _parse(self, raw: str) -> list[str]:
        """Parse a numbered list into at most 3 question strings."""
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        questions: list[str] = []
        for line in lines:
            cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            if cleaned:
                questions.append(cleaned)
        return questions[:3]
