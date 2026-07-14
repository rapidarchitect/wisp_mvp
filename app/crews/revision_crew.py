"""CrewAI crew that revises a compiled domain narrative per reviewer prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


class RevisionCrew(CrewBase):
    """Revise a compiled narrative according to a reviewer prompt."""

    def __init__(
        self,
        db: TenantDB | None,
        *,
        domain_code: str,
        domain_name: str,
        current_narrative: str,
        conversation: list[dict[str, Any]],
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.current_narrative = current_narrative
        self.conversation = conversation
        self.llm = llm or create_llm()

    async def revise(self, revision_prompt: str) -> str:
        """Return a revised narrative paragraph."""
        return await self.run_with_retry(lambda: self._revise_once(revision_prompt), max_retries=1)

    async def _revise_once(self, revision_prompt: str) -> str:
        prompt = self._build_prompt(revision_prompt)
        raw = await self._call_llm(prompt)
        return raw.strip()

    def _build_prompt(self, revision_prompt: str) -> str:
        lines = [f"Domain: {self.domain_name} ({self.domain_code})"]
        lines.append("Current narrative:")
        lines.append(self.current_narrative)
        lines.append("Reviewer instruction:")
        lines.append(revision_prompt)
        lines.append(
            "Rewrite the current narrative as a single professional paragraph "
            "for a Written Information Security Program, incorporating the reviewer instruction. "
            "Return only the paragraph, with no headings or lists."
        )
        return "\n\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        result = self.llm.call(prompt)
        if isinstance(result, str):
            return result
        raise RuntimeError("LLM did not return a string response")
