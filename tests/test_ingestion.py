from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.db.models import Market, MarketSnapshot
from pmnews.ingestion.markets import ingest_markets, store_markets
from pmnews.sources.base import Category, NormalizedMarket, PricePoint, SourceError


def _market(source: str, external_id: str, probability: str = "0.5") -> NormalizedMarket:
    return NormalizedMarket(
        source=source,
        external_id=external_id,
        question=f"{source} question {external_id}?",
        category=Category.finance,
        probability=Decimal(probability),
        volume=Decimal("10"),
        volume_unit="contracts",
        history_ref=external_id,
    )


class FakeSource:
    def __init__(self, name: str, markets: list[NormalizedMarket] | None) -> None:
        self.name = name
        self._markets = markets

    async def fetch_markets(self, per_category: int) -> list[NormalizedMarket]:
        if self._markets is None:
            raise SourceError(f"{self.name}: unreachable")
        return self._markets

    async def fetch_price_history(
        self, history_ref: str, since: date | None = None
    ) -> list[PricePoint]:
        return []


async def test_same_external_id_on_two_platforms_are_different_markets(db: AsyncSession) -> None:
    await store_markets(db, [_market("kalshi", "X-1"), _market("manifold", "X-1")])
    await db.commit()

    sources = (await db.execute(select(Market.source).order_by(Market.source))).scalars().all()
    assert sources == ["kalshi", "manifold"]
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 2


async def test_store_is_idempotent_within_a_day(db: AsyncSession) -> None:
    await store_markets(db, [_market("kalshi", "X-1", "0.5")])
    await store_markets(db, [_market("kalshi", "X-1", "0.6")])
    await db.commit()

    market = await db.scalar(select(Market))
    assert market is not None
    assert market.probability == 0.6
    assert market.volume_unit == "contracts"
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 1


async def test_one_failing_source_does_not_stop_the_others(
    session_factory: async_sessionmaker[AsyncSession], db: AsyncSession
) -> None:
    sources = {
        "polymarket": FakeSource("polymarket", None),
        "kalshi": FakeSource("kalshi", [_market("kalshi", "K-1")]),
    }

    stored = await ingest_markets(session_factory, sources, per_category=10)

    assert stored == {"kalshi": 1}
    assert await db.scalar(select(func.count()).select_from(Market)) == 1
