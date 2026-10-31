from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from pmnews.sources.base import Category, SourceError
from pmnews.sources.http import PoliteClient
from pmnews.sources.kalshi import BASE_URL, KalshiSource, candle_to_point, normalize_event
from tests.conftest import load_fixture


@pytest.fixture
def kalshi() -> KalshiSource:
    return KalshiSource(PoliteClient("kalshi", min_interval=0.0))


async def test_fetch_markets_keeps_top_markets_per_category(
    kalshi: KalshiSource, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"{BASE_URL}/events").mock(
        return_value=httpx.Response(200, json=load_fixture("kalshi/events_page.json"))
    )

    markets = await kalshi.fetch_markets(per_category=2)

    assert route.calls.last.request.url.params["with_nested_markets"] == "true"
    by_category: dict[Category, list[str]] = {}
    for m in markets:
        by_category.setdefault(m.category, []).append(m.external_id)
    assert all(len(ids) <= 2 for ids in by_category.values())
    assert by_category[Category.geopolitics] == ["KXPERSONPRESMAM-45", "KXNEWPOPE-70-PPAR"]
    assert by_category[Category.finance][0] == "KXOAIANTH-40-ANTH"  # highest volume
    assert "KXAGICO-COMP-26Q3" not in {m.external_id for m in markets}  # finalized


async def test_normalised_fields(kalshi: KalshiSource, mock_http: respx.MockRouter) -> None:
    mock_http.get(f"{BASE_URL}/events").mock(
        return_value=httpx.Response(200, json=load_fixture("kalshi/events_page.json"))
    )

    anthropic = next(
        m for m in await kalshi.fetch_markets(per_category=5) if m.external_id.endswith("ANTH")
    )

    assert anthropic.source == "kalshi"
    assert anthropic.event_id == "KXOAIANTH-40"
    assert anthropic.question == "Will Open AI or Anthropic IPO first? — Anthropic"
    assert anthropic.probability == Decimal("0.9900")
    assert anthropic.volume_unit == "contracts"
    assert anthropic.history_ref == "KXOAIANTH/KXOAIANTH-40-ANTH"
    assert anthropic.url == "https://kalshi.com/markets/kxoaianth"


async def test_follows_cursor_up_to_max_pages(mock_http: respx.MockRouter) -> None:
    route = mock_http.get(f"{BASE_URL}/events").mock(
        return_value=httpx.Response(200, json={"events": [], "cursor": "next"})
    )

    await KalshiSource(PoliteClient("kalshi", min_interval=0.0), max_pages=3).fetch_markets(5)

    assert route.call_count == 3
    assert route.calls[1].request.url.params["cursor"] == "next"


async def test_unexpected_shape_raises_source_error(
    kalshi: KalshiSource, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"{BASE_URL}/events").mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(SourceError):
        await kalshi.fetch_markets(per_category=5)


def test_combo_and_unmapped_events_are_skipped() -> None:
    market = {"ticker": "T", "title": "Q?", "status": "active", "last_price_dollars": "0.5"}
    combo = {"event_ticker": "KXMVEX-1", "series_ticker": "KXMVEX", "category": "Sports"}
    weather = {
        "event_ticker": "KXRAIN-1",
        "series_ticker": "KXRAIN",
        "category": "Climate and Weather",
    }

    assert normalize_event({**combo, "markets": [market]}) == []
    assert normalize_event({**weather, "markets": [market]}) == []


def test_untraded_market_uses_bid_ask_midpoint() -> None:
    event = {
        "event_ticker": "E-1",
        "series_ticker": "E",
        "category": "Politics",
        "markets": [
            {
                "ticker": "E-1",
                "title": "Q?",
                "status": "active",
                "last_price_dollars": "0.0000",
                "yes_bid_dollars": "0.2000",
                "yes_ask_dollars": "0.3000",
            }
        ],
    }

    [market] = normalize_event(event)

    assert market.probability == Decimal("0.25")


async def test_price_history_is_dated_by_us_eastern_trading_day(
    kalshi: KalshiSource, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(
        f"{BASE_URL}/series/KXOAIANTH/markets/KXOAIANTH-40-ANTH/candlesticks"
    ).mock(return_value=httpx.Response(200, json=load_fixture("kalshi/candlesticks.json")))

    points = await kalshi.fetch_price_history("KXOAIANTH/KXOAIANTH-40-ANTH")

    assert route.calls.last.request.url.params["period_interval"] == "1440"
    # The first candle closes at 2026-10-22 00:00 EDT, so it covers 21 October.
    assert points[0].day == date(2026, 10, 21)
    assert points[0].probability == Decimal("0.9300")
    assert [p.day for p in points] == sorted(p.day for p in points)
    assert len(points) == 10  # the untraded last day falls back to the bid/ask midpoint


def test_candle_without_any_price_is_skipped() -> None:
    assert candle_to_point({"end_period_ts": 1792641600, "price": {}, "yes_bid": {}}) is None
