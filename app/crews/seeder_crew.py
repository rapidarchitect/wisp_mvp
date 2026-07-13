"""CrewAI crew that generates yes-no questions for a security domain."""

from app.ai.crew_base import CrewBase
from app.ai.llm_factory import create_llm
from app.db.tenant import TenantDB
from app.exceptions import ExternalServiceError


class SeederCrew:
    """Generate 5-10 yes-no questions for a single WISP domain."""

    def __init__(
        self,
        db: TenantDB,
        *,
        domain_id: int,
        domain_code: str,
        domain_name: str,
        llm=None,
    ) -> None:
        self.db = db
        self.domain_id = domain_id
        self.domain_code = domain_code
        self.domain_name = domain_name
        self._llm = llm

    def _get_llm(self):
        """Return the provided LLM or build one from configuration."""
        return self._llm if self._llm is not None else create_llm()

    def _build_prompt(self) -> str:
        return (
            f"You are a security compliance expert. Generate 5 to 10 concise "
            f"yes-or-no questions that an accounting firm should answer for the "
            f"'{self.domain_name}' security domain (code {self.domain_code}). "
            f"Return ONLY a JSON object with a single key 'questions' containing "
            f"a list of objects with a 'text' field. Example: "
            f"{{'questions': [{{'text': 'Is physical access to servers restricted?'}}]}}"
        )

    def _parse_questions(self, raw: str) -> list[str]:
        """Parse the LLM response into a list of question texts."""
        import orjson

        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        data = orjson.loads(cleaned)
        if "questions" not in data:
            raise ValueError("Missing 'questions' key")
        items = data["questions"]
        if not 5 <= len(items) <= 10:
            raise ValueError(f"Expected 5-10 questions, got {len(items)}")
        return [str(item["text"]) for item in items]

    async def seed_domain(self) -> dict:
        """Create questions for the domain and return the count.

        On LLM failure or bad output, marks the domain as pending_questions
        so seeding can be retried later (C-19).
        """
        llm = self._get_llm()
        prompt = self._build_prompt()

        try:
            raw = await CrewBase.run_with_retry(
                lambda: self._call_llm(llm, prompt),
                max_retries=1,
            )
            questions = self._parse_questions(raw)
        except Exception as exc:  # noqa: BLE001
            await self.db.execute(
                "UPDATE domains SET status = ? WHERE id = ?",
                ("pending_questions", self.domain_id),
            )
            await self.db.commit()
            return {
                "domain_id": self.domain_id,
                "seeded": 0,
                "status": "pending_questions",
                "error": str(exc),
            }

        for idx, text in enumerate(questions):
            await self.db.execute(
                """
                INSERT INTO questions (domain_id, text, answer_type, origin, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.domain_id, text, "yes_no", "seeded", idx),
            )
        await self.db.execute(
            "UPDATE domains SET status = ? WHERE id = ?",
            ("ready", self.domain_id),
        )
        await self.db.commit()
        return {
            "domain_id": self.domain_id,
            "seeded": len(questions),
            "status": "ready",
        }

    async def _call_llm(self, llm, prompt: str) -> str:
        """Invoke the LLM and return the response text."""
        result = llm.call(prompt)
        if isinstance(result, str):
            return result
        raise ExternalServiceError("LLM did not return a string response")
