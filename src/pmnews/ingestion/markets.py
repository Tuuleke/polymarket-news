"""Scheduled ingestion: fetch every enabled source and store markets with a daily snapshot."""

import logging
from collections.abc import Mapping, Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.core.clock import utc_now, utc_today
from pmnews.db.models import Market, MarketSnapshot
from pmnews.sources.base import MarketSource, NormalizedMarket, SourceError

logger = logging.getLogger(__name__)


async def store_markets(session: AsyncSession, markets: Sequence[NormalizedMarket]) -> int:
    """Upsert markets by (source, external_id) and record today's probability once per day."""
    today = utc_today()
    for m in markets:
        values = {
            "source": m.source,
            "external_id": m.external_id,
            "event_id": m.event_id,
            "history_ref": m.history_ref,
            "question": m.question,
            "category": m.category.value,
            "probability": float(m.probability),
            "volume": float(m.volume),
            "volume_unit": m.volume_unit,
            "end_date": m.close_time,
            "url": m.url,
            "fetched_at": utc_now(),
        }
        market_id = (
            await session.execute(
                pg_insert(Market)
                .values(**values)
                .on_conflict_do_update(constraint="uq_markets_source_external_id", set_=values)
                .returning(Market.id)
            )
        ).scalar_one()
        await session.execute(
            pg_insert(MarketSnapshot)
            .values(market_id=market_id, date=today, probability=float(m.probability))
            .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
        )
    return len(markets)


async def ingest_markets(
    session_factory: async_sessionmaker[AsyncSession],
    sources: Mapping[str, MarketSource],
    per_category: int,
) -> dict[str, int]:
    """
    Fetch and store each source independently: one failing platform must not stop the others.
    NO LLM calls — article generation is triggered separately.
    """
    stored: dict[str, int] = {}
    for name, source in sources.items():
        try:
            markets = await source.fetch_markets(per_category)
        except SourceError as exc:
            logger.error("ingest: %s failed: %s", name, exc)
            continue
        async with session_factory() as session:
            stored[name] = await store_markets(session, markets)
            await session.commit()
        logger.info("ingest: %s stored %d markets", name, stored[name])
    return stored
