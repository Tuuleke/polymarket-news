import httpx
import respx

from pmnews.sources.polymarket import PolymarketService
from tests.conftest import CLOB_TEST_URL, GAMMA_TEST_URL, load_fixture


async def test_fetch_markets_by_tag_queries_gamma_with_tag_id(
    polymarket: PolymarketService, mock_http: respx.MockRouter
) -> None:
    route = mock_http.get(f"{GAMMA_TEST_URL}/markets").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/markets_geopolitics.json"))
    )

    markets = await polymarket.fetch_markets_by_tag("geopolitics", limit=10)

    assert [m["id"] for m in markets] == ["516710", "538932"]
    params = route.calls.last.request.url.params
    assert params["tag_id"] == "2"
    assert params["limit"] == "10"
    assert params["closed"] == "false"


async def test_unknown_tag_makes_no_request(polymarket: PolymarketService) -> None:
    with respx.mock(assert_all_mocked=True):
        assert await polymarket.fetch_markets_by_tag("sports") == []


async def test_price_history_returns_points(
    polymarket: PolymarketService, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/prices_history.json"))
    )

    history = await polymarket.fetch_price_history("token-1")

    assert len(history) == 5
    assert history[0] == {"t": 1775520000, "p": 0.72}


async def test_price_history_is_empty_when_clob_is_unavailable(
    polymarket: PolymarketService, mock_http: respx.MockRouter
) -> None:
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(side_effect=httpx.ConnectTimeout("x"))

    assert await polymarket.fetch_price_history("token-1") == []
