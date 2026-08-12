"""Centralized typed settings loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed application configuration. Secrets must come from the environment."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Real Estate Booking System"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api"

    jwt_secret: str = Field(..., min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    db_user: str = "root"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "realestate_db"
    database_url: str | None = None

    google_client_id: str = ""
    google_maps_api_key: str = ""

    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    booking_request_expire_hours: int = 48
    booking_payment_expire_hours: int = 24
    default_deposit_percent: float = 0.10

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder_secret(cls, value: str) -> str:
        placeholders = {
            "change-me-to-a-long-random-secret",
            "your-secret-key-here",
            "secret",
            "changeme",
        }
        if value.strip().lower() in placeholders:
            raise ValueError(
                "JWT_SECRET must be set to a strong random value "
                "(see backend/.env.example)."
            )
        return value

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        if self.environment.lower() == "production" and "*" in self.cors_origins_list:
            raise ValueError("CORS wildcards are not allowed in production")
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Never silently expand bare "*" with credentials — keep explicit list only
        return [o for o in origins if o != "*"] or ["http://localhost:3000"]

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+aiomysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
