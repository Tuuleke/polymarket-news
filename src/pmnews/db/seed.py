"""
Load the thesis sample markets so a fresh clone has something to show.

Usage: `make seed`, or `python -m pmnews.db.seed` with DATABASE_URL pointing at a migrated
database. Safe to run repeatedly: markets are upserted and existing snapshots are kept.
"""

import asyncio
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.db.models import Market, MarketSnapshot

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).parent / "seed_data" / "thesis_sample_2026-04.json"


def load_seed_markets(path: Path = SEED_FILE) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = json.loads(path.read_text())["markets"]
    return markets


async def seed(
    session_factory: async_sessionmaker[AsyncSession], markets: list[dict[str, Any]]
) -> int:
    async with session_factory() as session:
        for item in markets:
            snapshots = [(date.fromisoformat(d), p) for d, p in item["snapshots"]]
            last_day = max(d for d, _ in snapshots)
            values = {
                "source": "polymarket",
                "external_id": item["slug"],
                "volume_unit": "usd",
                "question": item["question"],
                "category": item["category"],
                "probability": item["probability"],
                "volume": item["volume"],
                "fetched_at": datetime.combine(last_day, datetime.min.time(), tzinfo=UTC),
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
                .values(
                    [{"market_id": market_id, "date": d, "probability": p} for d, p in snapshots]
                )
                .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
            )
        await session.commit()
    return len(markets)


async def _main() -> None:
    from pmnews.db.database import AsyncSessionLocal, engine

    count = await seed(AsyncSessionLocal, load_seed_markets())
    await engine.dispose()
    logger.info("Seeded %d thesis sample markets", count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
    asyncio.run(_main())
