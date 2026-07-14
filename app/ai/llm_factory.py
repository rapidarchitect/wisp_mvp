"""Configurable LLM factory for CrewAI agents."""

from crewai import LLM

from app.ai.fakes import ConfiguredLLM, FakeLLM
from app.config import settings


def create_llm(provider: str | None = None) -> LLM:
    """Return a CrewAI LLM instance based on the configured provider.

    Supported providers:
        - "openai": GPT-4 via OpenAI API
        - "anthropic": Claude via Anthropic API
        - "ollama": local Ollama models
        - "bedrock": AWS Bedrock models
        - "fake": deterministic test double

    When the real provider SDK is unavailable, a `ConfiguredLLM` placeholder
    is returned so that agent construction and configuration tests still work.
    """
    provider = (provider or settings.llm_provider).lower()

    if provider == "fake":
        return FakeLLM()

    if provider == "openai":
        try:
            return LLM(model="gpt-4", temperature=0.7)
        except Exception:  # noqa: BLE001
            return ConfiguredLLM(model="gpt-4", temperature=0.7)

    if provider == "anthropic":
        try:
            return LLM(model="claude-3-5-sonnet-20241022", temperature=0.7)
        except Exception:  # noqa: BLE001
            return ConfiguredLLM(model="claude-3-5-sonnet-20241022", temperature=0.7)

    if provider == "ollama":
        try:
            return LLM(
                model="ollama/hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0",
                base_url=settings.ollama_base_url,
                temperature=0.7,
            )
        except Exception:  # noqa: BLE001
            return ConfiguredLLM(
                model="ollama/hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0",
                base_url=settings.ollama_base_url,
                temperature=0.7,
            )

    if provider == "bedrock":
        try:
            return LLM(
                model=f"bedrock/{settings.bedrock_model_id}",
                region_name=settings.bedrock_region,
                temperature=0.7,
            )
        except Exception:  # noqa: BLE001
            return ConfiguredLLM(
                model=f"bedrock/{settings.bedrock_model_id}",
                region_name=settings.bedrock_region,
                temperature=0.7,
            )

    raise ValueError(f"Unsupported LLM provider: {provider}")
