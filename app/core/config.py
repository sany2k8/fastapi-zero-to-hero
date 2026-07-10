"""Application configuration via Pydantic Settings.

Values come from environment variables (or a `.env` file), so the same image
runs unchanged across dev/staging/prod — only the environment differs.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "dev-only-secret-key-change-me"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "TaskHub API"
    app_version: str = "1.0.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite+aiosqlite:///./taskhub.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # Auth
    secret_key: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS / trusted hosts
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["Authorization", "Content-Type", "X-Request-ID"]
    allowed_hosts: list[str] = ["*"]

    # Rate limiting (in-memory sliding window; swap for Redis when scaling out)
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    login_rate_limit_requests: int = 10
    login_rate_limit_window_seconds: int = 60

    # File uploads
    upload_dir: Path = Path("uploads")
    max_upload_size_bytes: int = 5 * 1024 * 1024
    allowed_upload_content_types: list[str] = [
        "image/png",
        "image/jpeg",
        "application/pdf",
        "text/plain",
        "text/csv",
    ]

    # Logging
    log_level: str = "INFO"
    log_json: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @model_validator(mode="after")
    def _forbid_insecure_production(self) -> "Settings":
        if self.is_production and self.secret_key == INSECURE_DEFAULT_SECRET:
            raise ValueError("SECRET_KEY must be set to a real secret in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance, used both directly and as a FastAPI dependency."""
    return Settings()
