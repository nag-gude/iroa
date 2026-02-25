"""IROA configuration from environment."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from iroa.env_loader import get_dotenv_path


class Settings(BaseSettings):
    """Application settings loaded from env and .env file in the project root."""

    model_config = SettingsConfigDict(
        env_file=str(get_dotenv_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_cloud_id: str | None = None  # Elastic Cloud: use with api_key or user/password
    elasticsearch_api_key: str | None = None
    elasticsearch_user: str | None = None
    elasticsearch_password: str | None = None
    iroa_log_index_pattern: str = "logs-*"
    iroa_metrics_index_pattern: str = "metrics-*"
    iroa_llm_api_url: str | None = None
    iroa_llm_api_key: str | None = None
    iroa_llm_model: str = "gpt-4o-mini"
    jira_base_url: str | None = None
    jira_api_token: str | None = None
    jira_email: str | None = None


def get_settings() -> Settings:
    return Settings()
