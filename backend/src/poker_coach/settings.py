from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    database_url: str = Field(
        default=f"sqlite:///{REPO_ROOT / 'data' / 'poker.db'}",
    )


settings = Settings()
