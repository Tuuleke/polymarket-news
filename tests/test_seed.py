from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.db.models import Market, MarketSnapshot
from pmnews.db.seed import load_seed_markets, seed


async def test_seed_loads_thesis_markets_and_is_repeatable(
    session_factory: async_sessionmaker[AsyncSession], db: AsyncSession
) -> None:
    markets = load_seed_markets()
    assert await seed(session_factory, markets) == 8
    assert await seed(session_factory, markets) == 8

    assert await db.scalar(select(func.count()).select_from(Market)) == 8
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 18
    fed = await db.scalar(
        select(Market).where(Market.polymarket_id == "thesis-fed-hold-april-2026")
    )
    assert fed is not None
    assert fed.probability == 0.99
