from pydantic import SecretStr
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

    # Scheduler
    FETCH_INTERVAL_MINUTES: int = 30


settings = Settings()
