import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pmnews.api.deps import get_news_source, get_sources
from pmnews.api.routes import articles, markets
from pmnews.core.clock import utc_now
from pmnews.core.config import settings
from pmnews.db.database import AsyncSessionLocal
from pmnews.ingestion.markets import ingest_markets
from pmnews.ingestion.news import ingest_news

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _scheduled_fetch() -> None:
    await ingest_markets(AsyncSessionLocal, get_sources(), settings.MARKETS_PER_CATEGORY)
    if settings.NEWS_ENABLED:
        await ingest_news(AsyncSessionLocal, get_news_source())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.SOURCES_ENABLED or settings.NEWS_ENABLED:
        _scheduler.add_job(
            _scheduled_fetch,
            "interval",
            minutes=settings.FETCH_INTERVAL_MINUTES,
            id="fetch_markets",
            replace_existing=True,
            next_run_time=utc_now(),  # first run in the background; startup does not wait
        )
        _scheduler.start()
    else:
        logger.info("No sources or news enabled — serving existing DB data only")
    yield
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered news platform for prediction market data",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router, prefix="/api/v1/articles", tags=["articles"])
app.include_router(markets.router, prefix="/api/v1/markets", tags=["markets"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
