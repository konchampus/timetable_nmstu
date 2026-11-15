import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: str = Field(repr=False)
    bot_token: str = Field(repr=False)
    mini_app_url: str
    allowed_origins: list[str]
    allowed_hosts: list[str]
    admin_ids: list[int] = []
    auth_max_age: int = Field(default=300, ge=30, le=3600)
    session_seconds: int = Field(default=3600, ge=300, le=86400)
    source_access_mode: Literal["public_viewer", "robots"] = "public_viewer"
    source_ttl_seconds: int = Field(default=900, ge=60)
    source_max_age_seconds: int = Field(default=86400, ge=900)
    source_timeout_seconds: int = Field(default=15, ge=2, le=60)
    source_request_spacing: float = Field(default=1.0, ge=0.2)
    timezone: str = "Asia/Yekaterinburg"
    worker_interval_seconds: int = Field(default=20, ge=5, le=60)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "postgresql+asyncpg" or not parts.hostname or not parts.username or not parts.password or not parts.path.strip("/"):
            raise ValueError("DATABASE_URL must contain asyncpg host/database and dedicated credentials")
        if parts.username in ("postgres", "root") or parts.password in ("companion", "password", "postgres", "changeme"):
            raise ValueError("Use dedicated non-superuser database credentials")
        return value

    @field_validator("bot_token")
    @classmethod
    def token_format(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]{4,15}:[A-Za-z0-9_-]{30,}", value):
            raise ValueError("BOT_TOKEN must be configured with a BotFather token")
        return value

    @field_validator("mini_app_url")
    @classmethod
    def https_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("MINI_APP_URL must be an HTTPS URL without credentials/query/fragment")
        return value.rstrip("/")

    @field_validator("allowed_origins")
    @classmethod
    def origins(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("Explicit ALLOWED_ORIGINS required")
        for value in values:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or "*" in value:
                raise ValueError("CORS origins must be exact HTTPS origins without trailing slash")
        return values

    @field_validator("allowed_hosts")
    @classmethod
    def hosts(cls, values: list[str]) -> list[str]:
        if not values or any(not re.fullmatch(r"[A-Za-z0-9.-]+", value) or "*" in value for value in values):
            raise ValueError("Explicit ALLOWED_HOSTS hostnames required; wildcards forbidden")
        return values

    @field_validator("timezone")
    @classmethod
    def university_timezone(cls, value: str) -> str:
        if value != "Asia/Yekaterinburg":
            raise ValueError("University timetable requires Asia/Yekaterinburg")
        ZoneInfo(value)
        return value

    @model_validator(mode="after")
    def consistent(self):
        parsed = urlsplit(self.mini_app_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.allowed_origins or parsed.hostname not in self.allowed_hosts:
            raise ValueError("MINI_APP_URL must match configured allowed origin and host")
        if self.source_max_age_seconds <= self.source_ttl_seconds:
            raise ValueError("SOURCE_MAX_AGE_SECONDS must exceed source TTL")
        return self


@lru_cache
def get_config() -> Config:
    return Config()


config = get_config()
