"""
Kalshi adapter: public, read-only market data only (events, markets, daily candlesticks).
No account, no API key and no trading endpoints are used.

Quirks handled here:
- Listing goes through /events with nested markets. The flat /markets listing is
  dominated by zero-volume multi-leg "combo" markets (KXMVE… tickers).
- Prices are fixed-point dollar strings ("0.9900"); a YES contract pays $1, so the
  price is the market-implied probability. Volume is counted in contracts, not dollars.
- Multi-outcome questions are split into one binary market per outcome under one event;
  for those the outcome name (yes_sub_title) is always appended, because the market
  titles alone are often identical or name every outcome.
- Daily candles close at midnight US Eastern and carry no traded price on days without
  trades; then the bid/ask midpoint is used, and days with neither are skipped.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from pmnews.core.clock import from_unix, parse_iso_utc, utc_now
from pmnews.sources.base import Category, NormalizedMarket, PricePoint, SourceError
from pmnews.sources.http import PoliteClient

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
EASTERN = ZoneInfo("America/New_York")
HISTORY_DEFAULT_DAYS = 90

CATEGORY_MAP: dict[str, Category] = {
    "Politics": Category.geopolitics,
    "Elections": Category.geopolitics,
    "World": Category.geopolitics,
    "Economics": Category.finance,
    "Financials": Category.finance,
    "Companies": Category.finance,
    "Crypto": Category.finance,
    "Science and Technology": Category.tech,
    "Entertainment": Category.culture,
    "Sports": Category.culture,
    "Social": Category.culture,
}


def _dollars(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed > 0 else None


def _probability(market: dict[str, Any]) -> Decimal | None:
    last = _dollars(market.get("last_price_dollars"))
    if last is not None:
        return last
    bid, ask = _dollars(market.get("yes_bid_dollars")), _dollars(market.get("yes_ask_dollars"))
    return (bid + ask) / 2 if bid is not None and ask is not None else None


def _question(market: dict[str, Any], multi_outcome: bool) -> str:
    title = str(market["title"]).strip()
    outcome = str(market.get("yes_sub_title") or "").strip()
    return f"{title} — {outcome}" if multi_outcome and outcome else title


def normalize_event(event: dict[str, Any]) -> list[NormalizedMarket]:
    category = CATEGORY_MAP.get(event.get("category", ""))
    if category is None or str(event.get("event_ticker", "")).startswith("KXMVE"):
        return []
    series = str(event["series_ticker"])
    raw_markets = event.get("markets") or []
    markets = []
    for m in raw_markets:
        probability = _probability(m)
        if m.get("status") != "active" or probability is None or m.get("mve_collection_ticker"):
            continue
        markets.append(
            NormalizedMarket(
                source="kalshi",
                external_id=m["ticker"],
                event_id=event["event_ticker"],
                question=_question(m, multi_outcome=len(raw_markets) > 1),
                category=category,
                probability=probability,
                volume=_dollars(m.get("volume_fp")) or Decimal(0),
                volume_unit="contracts",
                close_time=parse_iso_utc(m["close_time"]) if m.get("close_time") else None,
                url=f"https://kalshi.com/markets/{series.lower()}",
                history_ref=f"{series}/{m['ticker']}",
            )
        )
    return markets


def candle_to_point(candle: dict[str, Any]) -> PricePoint | None:
    closes_at = from_unix(candle["end_period_ts"]).astimezone(EASTERN)
    day = (closes_at - timedelta(seconds=1)).date()
    price = _dollars((candle.get("price") or {}).get("close_dollars"))
    if price is None:
        bid = _dollars((candle.get("yes_bid") or {}).get("close_dollars"))
        ask = _dollars((candle.get("yes_ask") or {}).get("close_dollars"))
        price = (bid + ask) / 2 if bid is not None and ask is not None else None
    return PricePoint(day=day, probability=price) if price is not None else None


class KalshiSource:
    name = "kalshi"

    def __init__(self, client: PoliteClient, max_pages: int = 10) -> None:
        self._client = client
        self._max_pages = max_pages

    async def fetch_markets(self, per_category: int) -> list[NormalizedMarket]:
        found: list[NormalizedMarket] = []
        cursor = ""
        for _ in range(self._max_pages):
            params: dict[str, str | int] = {
                "limit": 200,
                "status": "open",
                "with_nested_markets": "true",
            }
            if cursor:
                params["cursor"] = cursor
            page = await self._client.get_json(
                f"{BASE_URL}/events", endpoint="events", params=params
            )
            if not isinstance(page, dict) or "events" not in page:
                raise SourceError("kalshi: unexpected /events response shape")
            for event in page["events"]:
                found.extend(normalize_event(event))
            cursor = page.get("cursor") or ""
            if not cursor:
                break
        return _top_per_category(found, per_category)

    async def fetch_price_history(
        self, history_ref: str, since: date | None = None
    ) -> list[PricePoint]:
        series, _, ticker = history_ref.partition("/")
        end = utc_now()
        start = (
            datetime.combine(since, datetime.min.time(), tzinfo=EASTERN)
            if since
            else end - timedelta(days=HISTORY_DEFAULT_DAYS)
        )
        data = await self._client.get_json(
            f"{BASE_URL}/series/{series}/markets/{ticker}/candlesticks",
            endpoint="candlesticks",
            params={
                "start_ts": int(start.timestamp()),
                "end_ts": int(end.timestamp()),
                "period_interval": 1440,
            },
        )
        points = [p for c in data.get("candlesticks", []) if (p := candle_to_point(c))]
        return sorted((p for p in points if since is None or p.day >= since), key=lambda p: p.day)


def _top_per_category(markets: list[NormalizedMarket], n: int) -> list[NormalizedMarket]:
    ranked = sorted(markets, key=lambda m: m.volume, reverse=True)
    counts: dict[Category, int] = {}
    top = []
    for m in ranked:
        if counts.get(m.category, 0) < n:
            counts[m.category] = counts.get(m.category, 0) + 1
            top.append(m)
    return top
