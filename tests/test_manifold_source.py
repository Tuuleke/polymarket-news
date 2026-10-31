from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from pmnews.sources.base import Category
from pmnews.sources.http import PoliteClient
from pmnews.sources.manifold import BASE_URL, ManifoldSource, normalize_market
from tests.conftest import load_fixture

SEARCH = f"{BASE_URL}/search-markets"


@pytest.fixture
def manifold() -> ManifoldSource:
    return ManifoldSource(PoliteClient("manifold", min_interval=0.0, max_attempts=1))


def _mock_topics(mock_http: respx.MockRouter) -> None:
    tech = load_fixture("manifold/search_technology.json")
    for slug in ("technology", "ai"):  # the same markets under two slugs
        mock_http.get(SEARCH, params__contains={"topicSlug": slug}).mock(
            return_value=httpx.Response(200, json=tech)
        )
    mock_http.get(SEARCH, params__contains={"topicSlug": "geopolitics"}).mock(
        return_value=httpx.Response(500, json={"message": "An unexpected error occurred."})
    )
    mock_http.get(SEARCH).mock(return_value=httpx.Response(200, json=[]))


async def test_fetch_markets_maps_topics_and_skips_failing_ones(
    manifold: ManifoldSource, mock_http: respx.MockRouter
) -> None:
    _mock_topics(mock_http)

    markets = await manifold.fetch_markets(per_category=5)

    assert [m.external_id for m in markets] == ["PAZRpyZQuA", "yOsLEgU06A"]  # deduplicated
    assert {m.category for m in markets} == {Category.tech}
    first = markets[0]
    assert first.volume_unit == "mana"
    assert first.probability == Decimal("0.0058801381212468615")
    assert first.url is not None
    assert first.url.startswith("https://manifold.markets/")
    assert first.close_time is not None


async def test_price_history_is_the_last_bet_of_each_utc_day(
    manifold: ManifoldSource, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"{BASE_URL}/bets").mock(
        return_value=httpx.Response(200, json=load_fixture("manifold/bets.json"))
    )

    points = await manifold.fetch_price_history("PAZRpyZQuA")
    recent = await manifold.fetch_price_history("PAZRpyZQuA", since=date(2026, 10, 27))

    assert route.calls.last.request.url.params["contractId"] == "PAZRpyZQuA"
    assert [p.day for p in points] == [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)]
    assert points[-1].probability == Decimal("0.0058801381212468615")
    assert [p.day for p in recent] == [date(2026, 10, 27), date(2026, 10, 28)]


@pytest.mark.parametrize(
    "override",
    [{"outcomeType": "MULTIPLE_CHOICE"}, {"isResolved": True}, {"token": "CASH"}],
)
def test_non_binary_resolved_and_cash_markets_are_skipped(override: dict[str, object]) -> None:
    raw = load_fixture("manifold/search_technology.json")[0] | override

    assert normalize_market(raw, Category.tech) is None
