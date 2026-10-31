"""Scheduled ingestion: fetch Polymarket markets and store them with a daily snapshot."""

import json
import logging
from contextlib import suppress
from datetime import date, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.db.models import Market, MarketSnapshot
from pmnews.sources.polymarket import PolymarketService, RawMarket

logger = logging.getLogger(__name__)

TAGS = ["geopolitics", "finance", "culture", "tech"]


async def upsert_markets(session: AsyncSession, raw_markets: list[RawMarket], tag: str) -> int:
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
            with suppress(ValueError):
                end_date = datetime.fromisoformat(end_date_raw.rstrip("Z"))

        # Parse clobTokenIds — stored as JSON string array e.g. '["123...","456..."]'
        clob_token_id: str | None = None
        with suppress(ValueError, IndexError, TypeError):
            token_ids = json.loads(raw.get("clobTokenIds") or "[]")
            clob_token_id = str(token_ids[0]) if token_ids else None

        market_values: dict[str, Any] = {
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
        market_id = (await session.execute(stmt)).scalar_one()

        snap_stmt = (
            pg_insert(MarketSnapshot)
            .values(market_id=market_id, date=today, probability=probability)
            .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
        )
        await session.execute(snap_stmt)
        count += 1
    return count


async def fetch_and_store_markets(
    session_factory: async_sessionmaker[AsyncSession],
    source: PolymarketService,
) -> None:
    """
    Fetch top 10 markets per tag from Polymarket and persist them.
    Upserts Market rows and inserts today's MarketSnapshot (once per day).
    NO LLM calls — article generation is button-only.
    """
    logger.info("Scheduler: fetching markets for tags: %s", TAGS)
    async with session_factory() as session:
        total = 0
        for tag in TAGS:
            try:
                raw_markets = await source.fetch_markets_by_tag(tag, limit=10)
            except Exception as exc:
                logger.error("Scheduler: fetch_markets_by_tag(%s) failed: %r", tag, exc)
                continue
            count = await upsert_markets(session, raw_markets, tag)
            logger.info("Scheduler: tag=%s processed %d markets", tag, count)
            total += count
        await session.commit()
    logger.info("Scheduler: total processed %d markets", total)
