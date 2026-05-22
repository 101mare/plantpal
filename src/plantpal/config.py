"""Centralized configuration. Every magic number lives here, sourced from env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    APP_ENV: str = "production"
    BASE_URL: str = "http://localhost:8000"
    DB_PATH: str = "data/plantpal.db"
    IMAGE_DIR: str = "data/images"
    STATIC_DIR: str = "static"  # built frontend (SPA), served by FastAPI

    # Secrets
    TOKEN_PEPPER: str = "dev-pepper-change-me"
    CSRF_SECRET: str = "dev-csrf-change-me"

    # Sessions
    SESSION_SOFT_CAP_DAYS: int = 90
    SESSION_HARD_CAP_DAYS: int = 180
    SESSION_RENEW_IF_OLDER_THAN_HOURS: int = 24
    SESSION_LAST_SEEN_DEBOUNCE_MIN: int = 5
    COOKIE_NAME: str = "plantpal_session"
    CSRF_COOKIE_NAME: str = "plantpal_csrf"

    # Tokens
    LOGIN_TOKEN_TTL_MIN: int = 30
    INVITE_TOKEN_TTL_DAYS: int = 14

    # Images
    IMG_SIZE_PX: int = 96
    IMG_MAX_UPLOAD_MB: int = 10
    IMG_MAX_PIXELS: int = 25_000_000

    # Reminders
    REMINDER_HOUR_BERLIN: int = Field(default=8, ge=0, le=23)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "PlantPal <noreply@localhost>"
    RESEND_RATE_PER_SEC: float = 5.0
    RESEND_MAX_RETRIES: int = 3

    # Rate limits "<count>/<window>" where window in s|m|h
    RL_LOGIN_REQUEST_EMAIL: str = "3/h"
    RL_LOGIN_REQUEST_IP: str = "10/h"
    RL_LOGIN_VERIFY_IP: str = "10/m"
    RL_REGISTER_IP: str = "10/h"
    RL_PLANT_MUTATION: str = "30/m"
    RL_IMAGE_UPLOAD: str = "5/m"
    # constant-time floor for login-request responses (anti-enumeration), ms
    AUTH_REQUEST_MIN_MS: int = 350

    # Litestream
    LITESTREAM_ENABLED: bool = False
    LITESTREAM_REPLICA_URL: str | None = None

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def secure_cookies(self) -> bool:
        # Secure cookies in prod; allow plain HTTP only for local dev.
        return self.is_production or self.BASE_URL.startswith("https://")

    def validate_runtime(self) -> None:
        """Fail fast on contradictory or unsafe production config."""
        if self.SESSION_HARD_CAP_DAYS < self.SESSION_SOFT_CAP_DAYS:
            raise ValueError("SESSION_HARD_CAP_DAYS must be >= SESSION_SOFT_CAP_DAYS")
        if self.IMG_SIZE_PX <= 0:
            raise ValueError("IMG_SIZE_PX must be positive")
        if self.IMG_MAX_UPLOAD_MB <= 0 or self.IMG_MAX_UPLOAD_MB > 50:
            raise ValueError("IMG_MAX_UPLOAD_MB must be in 1..50")
        if self.is_production:
            if not self.BASE_URL.startswith("https://"):
                raise ValueError("BASE_URL must be https:// in production")
            if "localhost" in self.BASE_URL or "127.0.0.1" in self.BASE_URL:
                raise ValueError("BASE_URL must not point to localhost in production")
            for name, value in (
                ("TOKEN_PEPPER", self.TOKEN_PEPPER),
                ("CSRF_SECRET", self.CSRF_SECRET),
            ):
                if value.startswith("dev-") or len(value) < 32:
                    raise ValueError(f"{name} must be a non-default value of >= 32 chars in prod")
            if not self.RESEND_API_KEY:
                raise ValueError("RESEND_API_KEY required in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
