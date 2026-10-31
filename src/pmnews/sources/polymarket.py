"""
Polymarket adapter (public read-only Gamma and CLOB APIs).

Disabled by default: Polymarket is not available in Estonia because of its regulatory
status, and its APIs are not reachable from there. Enable it only where access is
legal by adding "polymarket" to SOURCES_ENABLED. When the API cannot be reached the
adapter raises SourceError like any other source; it never tries to work around blocks.
"""

import json
import logging
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from pmnews.core.clock import from_unix, parse_iso_utc
from pmnews.sources.base import Category, NormalizedMarket, PricePoint
from pmnews.sources.http import PoliteClient

logger = logging.getLogger(__name__)

GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"

# Polymarket tag IDs for the four UI tabs (found by exploring the Gamma API).
TAG_IDS: dict[Category, str] = {
    Category.geopolitics: "2",
    Category.finance: "120",
    Category.culture: "596",
    Category.tech: "439",
}


def normalize_market(raw: dict[str, Any], category: Category) -> NormalizedMarket | None:
    try:
        probability = Decimal(str(json.loads(raw["outcomePrices"])[0]))
    except (KeyError, ValueError, IndexError, TypeError, InvalidOperation):
        logger.warning("polymarket: skipping market %s: unparseable outcomePrices", raw.get("id"))
        return None
    try:
        token_ids = json.loads(raw.get("clobTokenIds") or "[]")
    except ValueError:
        token_ids = []
    end_date = raw.get("endDate")
    slug = raw.get("slug")
    return NormalizedMarket(
        source="polymarket",
        external_id=str(raw["id"]),
        question=raw.get("question", ""),
        category=category,
        probability=probability,
        volume=Decimal(str(raw.get("volume") or 0)),
        volume_unit="usd",
        close_time=parse_iso_utc(end_date) if end_date else None,
        url=f"https://polymarket.com/market/{slug}" if slug else None,
        history_ref=str(token_ids[0]) if token_ids else None,
    )


class PolymarketSource:
    name = "polymarket"

    def __init__(self, client: PoliteClient) -> None:
        self._client = client

    async def fetch_markets(self, per_category: int) -> list[NormalizedMarket]:
        result = []
        for category, tag_id in TAG_IDS.items():
            rows = await self._client.get_json(
                f"{GAMMA_URL}/markets",
                endpoint="markets",
                params={
                    "tag_id": tag_id,
                    "order": "volume",
                    "ascending": "false",
                    "limit": per_category,
                    "active": "true",
                    "closed": "false",
                },
            )
            for raw in rows if isinstance(rows, list) else []:
                if market := normalize_market(raw, category):
                    result.append(market)
        return result

    async def fetch_price_history(
        self, history_ref: str, since: date | None = None
    ) -> list[PricePoint]:
        params: dict[str, str | int] = {"market": history_ref, "interval": "max", "fidelity": 1440}
        if since:
            params["since"] = int(datetime.combine(since, time.min, tzinfo=UTC).timestamp())
        data = await self._client.get_json(
            f"{CLOB_URL}/prices-history", endpoint="prices-history", params=params
        )
        by_day: dict[date, Decimal] = {}
        for point in data.get("history", []):
            ts = float(point["t"])
            # The CLOB API has returned both seconds and milliseconds.
            day = from_unix(ts / 1000 if ts > 1e10 else ts).date()
            by_day[day] = Decimal(str(point["p"]))
        return [PricePoint(day=d, probability=p) for d, p in sorted(by_day.items())]
