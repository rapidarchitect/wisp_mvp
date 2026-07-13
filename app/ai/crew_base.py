"""Reusable crew base with one-retry exponential backoff."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class CrewBase:
    """Base helper for running CrewAI crews with retry resilience."""

    @staticmethod
    async def run_with_retry(
        run: Callable[[], Awaitable[Any]],
        *,
        max_retries: int = 1,
        base_delay: float = 1.0,
    ) -> Any:
        """Execute an async crew runner with exponential backoff retries.

        Args:
            run: Async callable that executes the crew (e.g. crew.kickoff()).
            max_retries: Maximum number of retry attempts after the first failure.
            base_delay: Base seconds for exponential backoff (delay = base_delay * 2^attempt).

        Returns:
            The result of the successful run.

        Raises:
            The last exception if all attempts fail.
        """
        last_exception: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return await run()
            except Exception as exc:  # noqa: BLE001
                last_exception = exc
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "Crew run failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        assert last_exception is not None
        raise last_exception
