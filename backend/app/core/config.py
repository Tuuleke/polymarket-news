from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Polymarket News"
    VERSION: str = "0.1.0"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/polymarket_news"

    # Polymarket API
    POLYMARKET_GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_API_URL: str = "https://clob.polymarket.com"

    # LLM
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

    # Scheduler
    FETCH_INTERVAL_MINUTES: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
