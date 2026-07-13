"""Tavily web search tool wrapper."""

from tavily import TavilyClient

from app.config import settings


class TavilySearchTool:
    """Thin wrapper around TavilyClient for CrewAI tool usage."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.tavily_api_key
        if key is None:
            raise RuntimeError("TAVILY_API_KEY is not configured")
        self._client = TavilyClient(api_key=key)

    def search(self, query: str, max_results: int = 5) -> dict:
        """Run a Tavily search and return the raw response dict."""
        return self._client.search(query=query, max_results=max_results)
