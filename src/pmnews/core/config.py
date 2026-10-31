import os
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

KNOWN_SOURCES = ("kalshi", "manifold", "polymarket")


class Settings(BaseSettings):
    # PMNEWS_ENV_FILE="" disables .env loading (the test suite does this to stay hermetic).
    model_config = SettingsConfigDict(
        env_file=os.environ.get("PMNEWS_ENV_FILE", ".env") or None, extra="ignore"
    )

    PROJECT_NAME: str = "Polymarket News"
    VERSION: str = "0.2.0"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/polymarket_news"

    # Market data sources, comma-separated: kalshi, manifold, polymarket.
    # Polymarket is off by default: it is not available in Estonia (regulatory status).
    SOURCES_ENABLED: Annotated[list[str], NoDecode] = ["kalshi", "manifold"]
    MARKETS_PER_CATEGORY: int = 10
    KALSHI_MAX_PAGES: int = 10
    # Raw API responses land here unchanged (S3 in Phase 3).
    RAW_DATA_DIR: Path = Path("data/raw")

    # LLM
    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "deepseek/deepseek-v3.2"
    LLM_WEB_SEARCH: bool = True

    # Who may trigger paid LLM calls through the API:
    #   disabled — nobody (safe default); open — anyone (local development only);
    #   token — requests must send the X-Admin-Token header.
    GENERATION_MODE: Literal["disabled", "open", "token"] = "disabled"
    ADMIN_TOKEN: SecretStr = SecretStr("")
    # Upper bound on LLM calls a single generate-updates request may make.
    MAX_UPDATES_PER_REQUEST: int = 5

    # Scheduler
    FETCH_INTERVAL_MINUTES: int = 30

    @field_validator("SOURCES_ENABLED", mode="before")
    @classmethod
    def _split_sources(cls, value: object) -> object:
        if isinstance(value, str):
            return [name.strip().lower() for name in value.split(",") if name.strip()]
        return value

    @field_validator("SOURCES_ENABLED")
    @classmethod
    def _known_sources(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - set(KNOWN_SOURCES))
        if unknown:
            raise ValueError(f"unknown sources {unknown}; choose from {list(KNOWN_SOURCES)}")
        return value

    @model_validator(mode="after")
    def _token_mode_needs_a_token(self) -> Self:
        if self.GENERATION_MODE == "token" and not self.ADMIN_TOKEN.get_secret_value():
            raise ValueError("GENERATION_MODE=token requires ADMIN_TOKEN to be set")
        return self


settings = Settings()
