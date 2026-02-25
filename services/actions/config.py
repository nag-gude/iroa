"""Actions service: Jira and ticketing configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict

from iroa.env_loader import get_dotenv_path


class ActionsServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(get_dotenv_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jira_base_url: str | None = None
    jira_api_token: str | None = None
    jira_email: str | None = None
    jira_project_key: str = "IROA"
    port: int = 8002


def get_settings() -> ActionsServiceSettings:
    return ActionsServiceSettings()
