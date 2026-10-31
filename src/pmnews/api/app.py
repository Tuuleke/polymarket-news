import json
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import insert as pg_insert

from pmnews.api.routes import articles, markets
from pmnews.core.config import settings
from pmnews.db.database import AsyncSessionLocal, Base, engine
from pmnews.db.models import Market, MarketSnapshot  # noqa: F401 — registers models with Base
from pmnews.sources.polymarket import PolymarketService

logger = logging.getLogger(__name__)
_polymarket = PolymarketService()
_scheduler = AsyncIOScheduler()

TAGS = ["geopolitics", "finance", "culture", "tech"]


async def _upsert_markets(session, raw_markets: list[dict], tag: str) -> int:
    """Upsert a list of raw market dicts into the DB with the given tag as category."""
    today = date.today()
    count = 0
    for raw in raw_markets:
        try:
            outcome_prices = json.loads(raw.get("outcomePrices", "[0]"))
            probability = float(outcome_prices[0])
        except (ValueError, IndexError, TypeError):
            probability = 0.0

        end_date: datetime | None = None
        end_date_raw = raw.get("endDate") or raw.get("end_date")
        if end_date_raw:
            try:
                end_date = datetime.fromisoformat(end_date_raw.rstrip("Z"))
            except ValueError:
                pass

        # Parse clobTokenIds — stored as JSON string array e.g. '["123...","456..."]'
        clob_token_id: str | None = None
        try:
            token_ids = json.loads(raw.get("clobTokenIds") or "[]")
            clob_token_id = str(token_ids[0]) if token_ids else None
        except (ValueError, IndexError, TypeError):
            pass

        market_values = {
            "polymarket_id": str(raw["id"]),
            "clob_token_id": clob_token_id,
            "question": raw.get("question", ""),
            "category": tag,
            "probability": probability,
            "volume": float(raw.get("volume", 0) or 0),
            "end_date": end_date,
            "fetched_at": datetime.utcnow(),
        }

        stmt = (
            pg_insert(Market)
            .values(**market_values)
            .on_conflict_do_update(
                index_elements=["polymarket_id"],
                set_={k: v for k, v in market_values.items() if k != "polymarket_id"},
            )
            .returning(Market.id)
        )
        result = await session.execute(stmt)
        market_id = result.scalar_one()

        snap_stmt = (
            pg_insert(MarketSnapshot)
            .values(market_id=market_id, date=today, probability=probability)
            .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
        )
        await session.execute(snap_stmt)
        count += 1
    return count


async def _fetch_and_store_markets() -> None:
    """
    Scheduled job: fetch top 10 markets per tag from Polymarket and persist them.
    Upserts Market rows and inserts today's MarketSnapshot (once per day).
    NO LLM calls — article generation is button-only.
    """
    logger.info("Scheduler: fetching markets for tags: %s", TAGS)
    async with AsyncSessionLocal() as session:
        total = 0
        for tag in TAGS:
            try:
                raw_markets = await _polymarket.fetch_markets_by_tag(tag, limit=10)
            except Exception as exc:
                logger.error("Scheduler: fetch_markets_by_tag(%s) failed: %r", tag, exc)
                continue
            count = await _upsert_markets(session, raw_markets, tag)
            logger.info("Scheduler: tag=%s processed %d markets", tag, count)
            total += count
        await session.commit()
    logger.info("Scheduler: total processed %d markets", total)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables if they don't exist yet (dev convenience; use alembic for production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not settings.DISABLE_SCHEDULER:
        _scheduler.add_job(
            _fetch_and_store_markets,
            "interval",
            minutes=settings.FETCH_INTERVAL_MINUTES,
            id="fetch_markets",
            replace_existing=True,
        )
        _scheduler.start()
        await _fetch_and_store_markets()
    else:
        logger.info("Scheduler disabled — serving existing DB data only")
    yield
    if not settings.DISABLE_SCHEDULER:
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
async def health_check():
    return {"status": "ok"}
