"""Agent service: orchestrator URLs and timeout."""
from pydantic_settings import BaseSettings, SettingsConfigDict

from iroa.env_loader import get_dotenv_path


class AgentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(get_dotenv_path()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_service_url: str = "http://localhost:8001"
    actions_service_url: str = "http://localhost:8002"
    port: int = 8000
    timeout_seconds: float = 60.0


def get_settings() -> AgentServiceSettings:
    return AgentServiceSettings()
