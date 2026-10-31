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
    OPENROUTER_API_KEY: str = ""
    LLM_MODEL: str = "deepseek/deepseek-v3.2"
    LLM_WEB_SEARCH: bool = True
    # Scheduler
    FETCH_INTERVAL_MINUTES: int = 30
    DISABLE_SCHEDULER: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
