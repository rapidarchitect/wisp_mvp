"""CrewAI crew that compiles a domain conversation into a narrative answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm

if TYPE_CHECKING:
    from app.db.tenant import TenantDB


class CompilerCrew(CrewBase):
    """Compile a domain's questions, answers, and follow-up responses."""

    def __init__(
        self,
        db: TenantDB | None,
        *,
        domain_code: str,
        domain_name: str,
        conversation: list[dict[str, Any]],
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.domain_code = domain_code
        self.domain_name = domain_name
        self.conversation = conversation
        self.llm = llm or create_llm()

    async def compile(self) -> str:
        """Return a single WISP narrative paragraph for the domain."""
        return await self.run_with_retry(self._compile_once, max_retries=1)

    async def _compile_once(self) -> str:
        prompt = self._build_prompt()
        raw = await self._call_llm(prompt)
        return raw.strip()

    def _build_prompt(self) -> str:
        lines = [f"Domain: {self.domain_name} ({self.domain_code})"]
        lines.append(
            "Write a single professional paragraph for a Written Information Security Program "
            "that summarizes the following contributor input."
        )
        for item in self.conversation:
            lines.append(f"Question: {item['question']}")
            lines.append(f"Answer: {item['answer']}")
            for fu in item.get("followups", []):
                lines.append(f"Follow-up: {fu['text']}")
                lines.append(f"Response: {fu['response']}")
        lines.append("Return only the paragraph, with no headings or lists.")
        return "\n\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        result = self.llm.call(prompt)
        if isinstance(result, str):
            return result
        raise RuntimeError("LLM did not return a string response")
