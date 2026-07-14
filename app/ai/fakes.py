"""Deterministic test doubles for LLM and Tavily integrations."""

from typing import Any

from crewai import BaseLLM


class FakeLLM(BaseLLM):
    """Deterministic CrewAI LLM double for tests.

    Returns canned responses based on a lookup map. If no map is supplied,
    returns a default string. The failure mode can be toggled to raise on
    every call (used for retry tests).
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default: str | None = None,
        fail: bool = False,
    ) -> None:
        super().__init__(model="fake/test-model")
        self._responses = responses or {}
        self._default = default
        self._fail = fail

    def call(
        self,
        messages: str | list[dict[str, str]],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
    ) -> str:
        """Return a canned response or raise if failure mode is enabled."""
        if self._fail:
            raise RuntimeError("FakeLLM failure")

        prompt = messages if isinstance(messages, str) else str(messages)
        for key, response in self._responses.items():
            if key in prompt:
                return response

        if self._default is not None:
            return self._default

        # Deterministic fallback for E2E runs where no explicit default is set.
        prompt_lower = prompt.lower()
        followup_keywords = ("follow-up", "followup", "dig deeper")
        if any(k in prompt_lower for k in followup_keywords):
            return (
                "1. What controls enforce the restriction?\n"
                "2. fake-llm-response\n"
                "3. How often is access reviewed?"
            )
        if "reviewer instruction" in prompt_lower or "rewrite" in prompt_lower:
            return (
                "Access Control Policy: contributors answered yes to all questions, "
                "documented controls in their policy, and included more detail on access logs."
            )
        narrative_keywords = ("summarize", "narrative", "paragraph")
        if any(k in prompt_lower for k in narrative_keywords):
            return (
                "Access Control Policy: contributors answered yes to all questions "
                "and documented controls in their policy."
            )
        return "fake-llm-response"

    def supports_function_calling(self) -> bool:
        """Return False to keep tests simple."""
        return False

    def get_context_window_size(self) -> int:
        """Return a conservative context window."""
        return 4096


class ConfiguredLLM(BaseLLM):
    """Lightweight LLM placeholder that records provider configuration.

    CrewAI's native LLM providers (OpenAI, Anthropic, Bedrock, Ollama via
    LiteLLM) require optional SDKs that are not part of the approved dependency
    list. This class carries the intended configuration and can be passed to an
    Agent; its `call` raises if actually invoked without the real provider.
    """

    def __init__(self, *, model: str, **kwargs) -> None:
        super().__init__(model=model)
        self._config = {"model": model, **kwargs}
        for key, value in kwargs.items():
            setattr(self, key, value)

    def call(
        self,
        messages: str | list[dict[str, str]],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
    ) -> str:
        """Raise because the real provider SDK is not installed."""
        raise NotImplementedError(
            f"LLM provider for {self.model} is not installed in this environment"
        )

    def supports_function_calling(self) -> bool:
        """Return False to keep tests simple."""
        return False

    def get_context_window_size(self) -> int:
        """Return a conservative context window."""
        return 4096


class FakeTavilySearchTool:
    """Deterministic Tavily search double for tests."""

    def __init__(self, results: list[dict] | None = None) -> None:
        self._results = results or [
            {
                "title": "Fake result",
                "url": "https://example.com/fake",
                "content": "This is a fake Tavily result.",
                "score": 0.95,
            }
        ]
        self._fail = False

    def search(self, query: str, max_results: int = 5) -> dict:
        """Return deterministic search results."""
        if self._fail:
            raise RuntimeError("FakeTavily failure")
        return {
            "query": query,
            "results": self._results[:max_results],
        }

    def set_failure(self, fail: bool) -> None:
        """Toggle failure mode (useful for retry tests)."""
        self._fail = fail
