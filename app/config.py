"""Application configuration."""

import os

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """WISPGen settings loaded from environment variables."""

    model_config = ConfigDict(populate_by_name=True)

    env: str = Field(default="dev", alias="WISPGEN_ENV")
    data_dir: str = Field(default="./data", alias="WISPGEN_DATA_DIR")
    base_domain: str = Field(default="app.wisp.llc", alias="WISPGEN_BASE_DOMAIN")
    secret_key: str = Field(default="change-me", alias="WISPGEN_SECRET_KEY")
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-6", alias="BEDROCK_MODEL_ID"
    )
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    ses_region: str = Field(default="us-east-1", alias="SES_REGION")
    email_from: str = Field(default="noreply@app.wisp.llc", alias="EMAIL_FROM")
    email_backend: str = Field(default="console", alias="EMAIL_BACKEND")


def get_settings() -> Settings:
    """Return a settings instance populated from the environment."""
    return Settings.model_validate(os.environ)


settings = get_settings()
