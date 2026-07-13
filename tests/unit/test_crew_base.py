"""Unit tests for the crew base retry helper."""

import pytest

from app.ai.crew_base import CrewBase


async def test_run_with_retry_success():
    async def run():
        return "ok"

    result = await CrewBase.run_with_retry(run)
    assert result == "ok"


async def test_run_with_retry_recovers_after_one_failure(monkeypatch):
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.crew_base.asyncio.sleep", fake_sleep)

    calls = []

    async def run():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return "ok"

    result = await CrewBase.run_with_retry(run)
    assert result == "ok"
    assert len(calls) == 2
    assert sleeps == [1.0]


async def test_run_with_retry_surfaces_last_failure(monkeypatch):
    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("app.ai.crew_base.asyncio.sleep", fake_sleep)

    async def run():
        raise RuntimeError("persistent")

    with pytest.raises(RuntimeError, match="persistent"):
        await CrewBase.run_with_retry(run)


async def test_run_with_retry_exponential_backoff(monkeypatch):
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.crew_base.asyncio.sleep", fake_sleep)

    attempts = 0

    async def run():
        nonlocal attempts
        attempts += 1
        raise RuntimeError(f"fail {attempts}")

    with pytest.raises(RuntimeError):
        await CrewBase.run_with_retry(run, max_retries=2, base_delay=0.5)

    assert attempts == 3
    assert sleeps == [0.5, 1.0]
