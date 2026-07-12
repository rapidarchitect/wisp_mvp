"""Tests for app configuration."""

import os

from app.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Settings use sensible defaults when env vars are absent."""
    settings = Settings()
    assert settings.env == "dev"
    assert settings.data_dir == "./data"


def test_settings_from_env(monkeypatch) -> None:
    """Settings read from environment variables."""
    monkeypatch.setenv("WISPGEN_ENV", "test")
    monkeypatch.setenv("WISPGEN_DATA_DIR", "/tmp/wispgen")
    settings = get_settings()
    assert settings.env == "test"
    assert settings.data_dir == "/tmp/wispgen"


def test_settings_populate_by_name() -> None:
    """Settings can be constructed with field names, not just aliases."""
    settings = Settings(env="test")
    assert settings.env == "test"
    assert os.environ.get("WISPGEN_ENV") != "test" or settings.env == "test"
