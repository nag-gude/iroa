"""Data service: Elasticsearch connection and index patterns."""
from pydantic_settings import BaseSettings, SettingsConfigDict

from iroa.env_loader import get_dotenv_path


class DataServiceSettings(BaseSettings):
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
    port: int = 8001


def get_settings() -> DataServiceSettings:
    return DataServiceSettings()
