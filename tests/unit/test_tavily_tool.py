"""Unit tests for the Tavily tool wrapper and fake double."""

from unittest.mock import MagicMock, patch

import pytest

from app.ai.fakes import FakeTavilySearchTool
from app.ai.tavily_tool import TavilySearchTool


def test_fake_tavily_returns_results():
    fake = FakeTavilySearchTool(results=[{"title": "A", "content": "answer A"}])
    result = fake.search("query")
    assert result["query"] == "query"
    assert result["results"][0]["title"] == "A"


def test_fake_tavily_honors_max_results():
    fake = FakeTavilySearchTool(results=[{"title": f"R{i}", "content": str(i)} for i in range(5)])
    result = fake.search("query", max_results=2)
    assert len(result["results"]) == 2


def test_fake_tavily_failure_mode():
    fake = FakeTavilySearchTool()
    fake.set_failure(True)
    with pytest.raises(RuntimeError, match="FakeTavily failure"):
        fake.search("query")


def test_tavily_tool_raises_without_key():
    with (
        patch("app.ai.tavily_tool.settings.tavily_api_key", None),
        pytest.raises(RuntimeError, match="TAVILY_API_KEY"),
    ):
        TavilySearchTool()


def test_tavily_tool_delegates_to_client():
    mock_client = MagicMock()
    mock_client.search.return_value = {"results": [{"title": "Real"}]}

    with patch("app.ai.tavily_tool.TavilyClient", return_value=mock_client):
        tool = TavilySearchTool(api_key="test-key")
        result = tool.search("test query", max_results=3)

    assert result["results"][0]["title"] == "Real"
    mock_client.search.assert_called_once_with(query="test query", max_results=3)
