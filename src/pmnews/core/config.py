from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Polymarket News"
    VERSION: str = "0.2.0"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/polymarket_news"

    # Polymarket API. Off by default: Polymarket is not available in Estonia
    # (regulatory status), so the scheduled fetch only runs when explicitly enabled.
    POLYMARKET_ENABLED: bool = False
    POLYMARKET_GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_API_URL: str = "https://clob.polymarket.com"

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

    # Scheduler
    FETCH_INTERVAL_MINUTES: int = 30

    @model_validator(mode="after")
    def _token_mode_needs_a_token(self) -> Self:
        if self.GENERATION_MODE == "token" and not self.ADMIN_TOKEN.get_secret_value():
            raise ValueError("GENERATION_MODE=token requires ADMIN_TOKEN to be set")
        return self


settings = Settings()
