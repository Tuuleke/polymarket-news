from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from pmnews.sources.base import Category, SourceError
from pmnews.sources.polymarket import CLOB_URL, GAMMA_URL, PolymarketSource, normalize_market
from tests.conftest import load_fixture


async def test_fetch_markets_queries_each_tab_by_tag_id(
    polymarket: PolymarketSource, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"{GAMMA_URL}/markets", params__contains={"tag_id": "2"}).mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/markets_geopolitics.json"))
    )
    route = mock_http.get(f"{GAMMA_URL}/markets").mock(return_value=httpx.Response(200, json=[]))

    markets = await polymarket.fetch_markets(per_category=10)

    assert route.call_count == 3  # the other three tabs
    assert [m.external_id for m in markets] == ["516710", "538932"]
    newsom = markets[0]
    assert newsom.category is Category.geopolitics
    assert newsom.probability == Decimal("0.25")
    assert newsom.volume_unit == "usd"
    assert newsom.close_time == datetime(2028, 8, 31, 12, tzinfo=UTC)
    assert newsom.history_ref is not None
    assert newsom.history_ref.startswith("7132")


def test_market_with_unparseable_price_is_skipped() -> None:
    raw = load_fixture("polymarket/markets_geopolitics.json")[0] | {"outcomePrices": "not json"}

    assert normalize_market(raw, Category.geopolitics) is None


async def test_price_history_is_one_point_per_utc_day(
    polymarket: PolymarketSource, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"{CLOB_URL}/prices-history").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/prices_history.json"))
    )

    points = await polymarket.fetch_price_history("token-1", since=date(2026, 4, 7))

    assert route.calls.last.request.url.params["since"] == "1775520000"  # midnight UTC
    assert [p.day for p in points][:2] == [date(2026, 4, 7), date(2026, 4, 8)]
    assert points[-1].probability == Decimal("0.99")


async def test_unreachable_api_raises_source_error(
    polymarket: PolymarketSource, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"{CLOB_URL}/prices-history").mock(side_effect=httpx.ConnectTimeout("blocked"))

    with pytest.raises(SourceError, match="unreachable"):
        await polymarket.fetch_price_history("token-1")
