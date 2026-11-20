from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/keitaro_wrapper"
    keitaro_api_url: str = "https://tlgk.host/admin_api/v1"
    keitaro_default_api_key: str = ""
    default_campaign_prefix: str = "test_lukashov_"
    default_domain_id: int | None = None
    default_group_id: int | None = None
    default_traffic_source_id: int | None = None
    cookie_secure: bool = False
    session_ttl_hours: int = 24
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @field_validator(
        "default_domain_id",
        "default_group_id",
        "default_traffic_source_id",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
