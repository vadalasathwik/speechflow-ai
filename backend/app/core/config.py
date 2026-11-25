from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "SpeechFlow AI API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api"
    allowed_origins: list[AnyHttpUrl] = Field(default_factory=list)
    database_url: str = "postgresql+psycopg://speechflow:speechflow@localhost:5432/speechflow"


@lru_cache
def get_settings() -> Settings:
    return Settings()
