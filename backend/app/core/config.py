from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIRECTORY / ".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "SpeechFlow AI API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api"
    allowed_origins: list[AnyHttpUrl] = Field(default_factory=list)
    session_cookie_name: str = "speechflow_session"
    csrf_cookie_name: str = "speechflow_csrf"
    session_token_pepper: str = "development-only-change-me"
    session_duration_days: int = Field(default=30, ge=1, le=365)
    session_cookie_samesite: str = "lax"
    database_url: str = "postgresql+psycopg://speechflow:speechflow@localhost:5432/speechflow"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "auto"
    whisper_vad_filter: bool = True
    whisper_beam_size: int = Field(default=5, ge=1, le=10)
    whisper_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    whisper_condition_on_previous_text: bool = False
    whisper_enable_script_retry: bool = True
    whisper_warmup_on_start: bool = False
    max_audio_size_mb: int = Field(default=10, ge=1)
    max_audio_duration_seconds: int = Field(default=120, ge=1)
    max_concurrent_transcriptions: int = Field(default=1, ge=1)
    max_realtime_session_seconds: int = Field(default=300, ge=10)
    max_realtime_audio_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    realtime_window_seconds: float = Field(default=8.0, ge=2, le=30)
    realtime_overlap_seconds: float = Field(default=1.0, ge=0, le=5)

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.session_cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict, or none")
        if any(str(origin) == "*" for origin in self.allowed_origins):
            raise ValueError("ALLOWED_ORIGINS cannot include '*' when cookies are enabled")
        if self.environment == "production" and self.session_token_pepper == "development-only-change-me":
            raise ValueError("SESSION_TOKEN_PEPPER must be configured in production")
        if self.environment == "production" and self.session_cookie_samesite != "none" and len(self.allowed_origins) > 1:
            raise ValueError("cross-site deployments require SESSION_COOKIE_SAMESITE=none and HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
