from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.db.models import Market, MarketSnapshot
from pmnews.ingestion.polymarket import upsert_markets
from tests.conftest import load_fixture


async def test_upsert_inserts_markets_and_one_snapshot_each(db: AsyncSession) -> None:
    raw = load_fixture("polymarket/markets_geopolitics.json")

    count = await upsert_markets(db, raw, "geopolitics")
    await db.commit()

    assert count == 2
    markets = (await db.execute(select(Market).order_by(Market.polymarket_id))).scalars().all()
    assert [m.probability for m in markets] == [0.25, 0.99]
    assert markets[0].clob_token_id is not None
    assert markets[0].clob_token_id.startswith("7132")
    assert markets[0].category == "geopolitics"
    assert markets[0].end_date == datetime(2028, 8, 31, 12, tzinfo=UTC)
    assert markets[0].fetched_at.tzinfo is not None
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 2


async def test_upsert_is_idempotent_within_a_day(db: AsyncSession) -> None:
    raw = load_fixture("polymarket/markets_geopolitics.json")
    await upsert_markets(db, raw, "geopolitics")
    raw[0]["outcomePrices"] = '["0.30", "0.70"]'

    await upsert_markets(db, raw, "geopolitics")
    await db.commit()

    assert await db.scalar(select(func.count()).select_from(Market)) == 2
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 2
    newsom = await db.scalar(select(Market).where(Market.polymarket_id == "516710"))
    assert newsom is not None
    assert newsom.probability == 0.30
