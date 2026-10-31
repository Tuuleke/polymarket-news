from datetime import date, timedelta

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.api.app import app
from pmnews.api.deps import get_polymarket
from pmnews.api.routes.markets import find_significant_moves
from pmnews.core.clock import utc_today
from pmnews.core.config import settings
from pmnews.db.models import Article, Market, MarketSnapshot
from tests.conftest import CLOB_TEST_URL, load_fixture

pytestmark = pytest.mark.usefixtures("generation_open")


async def _add_market(db: AsyncSession, **overrides: object) -> Market:
    values: dict[str, object] = {
        "polymarket_id": "538932",
        "clob_token_id": "token-1",
        "question": "Will the Federal Reserve hold interest rates unchanged?",
        "category": "finance",
        "probability": 0.99,
        "volume": 128_000_000.0,
    }
    market = Market(**(values | overrides))
    db.add(market)
    await db.commit()
    return market


def _snap(day: int, p: float) -> MarketSnapshot:
    return MarketSnapshot(date=date(2026, 4, day), probability=p)


def test_find_significant_moves_uses_threshold_and_gap() -> None:
    snaps = [_snap(1, 0.50), _snap(2, 0.55), _snap(3, 0.70), _snap(9, 0.20)]

    moves = find_significant_moves(snaps, already_covered=set())

    # 2→3 moved 15pp; 3→9 moved 50pp but the 6-day gap is too wide to attribute.
    assert [(p.date.day, c.date.day) for p, c in moves] == [(2, 3)]


def test_find_significant_moves_skips_covered_dates() -> None:
    snaps = [_snap(2, 0.55), _snap(3, 0.70)]

    assert find_significant_moves(snaps, already_covered={date(2026, 4, 3)}) == []


async def test_list_markets_filters_by_category(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _add_market(db)
    await _add_market(db, polymarket_id="2", category="tech", volume=5.0)

    resp = await client.get("/api/v1/markets/", params={"category": "finance"})

    assert resp.status_code == 200
    assert [m["polymarket_id"] for m in resp.json()] == ["538932"]


async def test_get_market_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/markets/999")

    assert resp.status_code == 404


async def test_explain_creates_article(
    client: httpx.AsyncClient, db: AsyncSession, openrouter: respx.Route
) -> None:
    market = await _add_market(db)

    resp = await client.post(f"/api/v1/markets/{market.id}/explain")

    assert resp.status_code == 201
    assert resp.json()["title"] == "Fed Expected to Hold Rates in April"
    assert openrouter.call_count == 1


async def test_generate_updates_backfills_history_and_writes_articles(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mock_http: respx.MockRouter,
    openrouter: respx.Route,
) -> None:
    market = await _add_market(db)
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/prices_history.json"))
    )

    resp = await client.post(f"/api/v1/markets/{market.id}/generate-updates")

    assert resp.status_code == 201
    assert resp.json()["generated"] == 2
    assert openrouter.call_count == 2
    assert await db.scalar(select(func.count()).select_from(MarketSnapshot)) == 5
    assert await db.scalar(select(func.count()).select_from(Article)) == 2


async def test_snapshot_dates_are_utc_calendar_days(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mock_http: respx.MockRouter,
    openrouter: respx.Route,
) -> None:
    market = await _add_market(db)
    late_evening_utc = 1775520000 - 3600  # 2026-04-06 23:00 UTC = 2026-04-07 02:00 in Tallinn
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(
        return_value=httpx.Response(200, json={"history": [{"t": late_evening_utc, "p": 0.5}]})
    )

    await client.post(f"/api/v1/markets/{market.id}/generate-updates")

    snapshot = await db.scalar(select(MarketSnapshot))
    assert snapshot is not None
    assert snapshot.date == date(2026, 4, 6)


async def test_generate_updates_reports_only_new_snapshots(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mock_http: respx.MockRouter,
    openrouter: respx.Route,
) -> None:
    market = await _add_market(db)
    db.add(MarketSnapshot(market_id=market.id, date=date(2026, 4, 7), probability=0.72))
    await db.commit()
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/prices_history.json"))
    )

    resp = await client.post(f"/api/v1/markets/{market.id}/generate-updates")

    assert resp.json()["snapshots_added"] == 4


async def test_generate_updates_is_503_when_polymarket_is_disabled(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    market = await _add_market(db)
    del app.dependency_overrides[get_polymarket]  # use the real, settings-driven dependency

    resp = await client.post(f"/api/v1/markets/{market.id}/generate-updates")

    assert resp.status_code == 503


async def test_generate_updates_writes_at_most_the_configured_number_of_articles(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mock_http: respx.MockRouter,
    openrouter: respx.Route,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MAX_UPDATES_PER_REQUEST", 1)
    market = await _add_market(db)
    mock_http.get(f"{CLOB_TEST_URL}/prices-history").mock(
        return_value=httpx.Response(200, json=load_fixture("polymarket/prices_history.json"))
    )

    resp = await client.post(f"/api/v1/markets/{market.id}/generate-updates")

    assert resp.json()["dates"] == ["2026-04-11"]  # the most recent of the two moves
    assert openrouter.call_count == 1


async def test_market_detail_only_includes_recent_snapshots(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    market = await _add_market(db)
    today = utc_today()
    db.add_all(
        MarketSnapshot(market_id=market.id, date=today - timedelta(days=d), probability=0.5)
        for d in range(120)
    )
    await db.commit()

    resp = await client.get(f"/api/v1/markets/{market.id}")

    dates = [s["date"] for s in resp.json()["snapshots"]]
    assert len(dates) == 91  # today plus the 90 days before it
    assert min(dates) == (today - timedelta(days=90)).isoformat()


async def test_list_markets_paginates(client: httpx.AsyncClient, db: AsyncSession) -> None:
    for i in range(3):
        await _add_market(db, polymarket_id=str(i), volume=float(i))

    first = await client.get("/api/v1/markets/", params={"limit": 2})
    rest = await client.get("/api/v1/markets/", params={"limit": 2, "offset": 2})
    too_big = await client.get("/api/v1/markets/", params={"limit": 101})

    assert [m["polymarket_id"] for m in first.json()] == ["2", "1"]
    assert [m["polymarket_id"] for m in rest.json()] == ["0"]
    assert too_big.status_code == 422
