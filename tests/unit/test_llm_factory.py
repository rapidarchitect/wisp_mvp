"""Unit tests for the LLM factory."""

import pytest

from app.ai.fakes import ConfiguredLLM, FakeLLM
from app.ai.llm_factory import create_llm
from app.config import settings


def test_create_fake_llm():
    llm = create_llm("fake")
    assert isinstance(llm, FakeLLM)


def test_create_ollama_llm():
    llm = create_llm("ollama")
    assert llm.model == "ollama/hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0"
    assert llm.base_url == settings.ollama_base_url


def test_create_bedrock_llm():
    llm = create_llm("bedrock")
    assert llm.model == settings.bedrock_model_id
    assert llm.region_name == settings.bedrock_region


def test_create_openai_llm():
    llm = create_llm("openai")
    assert llm.model == "gpt-4"


def test_create_anthropic_llm():
    llm = create_llm("anthropic")
    assert isinstance(llm, ConfiguredLLM)
    assert llm.model == "claude-3-5-sonnet-20241022"


def test_create_llm_uses_default_provider():
    llm = create_llm()
    assert llm.model == "ollama/hf.co/unsloth/gemma-4-12B-it-GGUF:Q8_0"


def test_create_llm_unsupported_provider_raises():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_llm("unknown")
