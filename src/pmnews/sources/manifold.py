"""
Manifold Markets adapter (open API, no key; play-money "mana" markets).

Markets are found per UI tab through Manifold topic slugs. Some slugs that look
plausible ("politics", "economics", "world") return HTTP 500, so the mapping only uses
slugs verified on 2026-10-31, and a failing topic is logged and skipped.

Manifold has no candlestick endpoint. Daily history is derived from the most recent
bets: each bet records the market probability after it (probAfter), and the last bet
of each UTC day is that day's closing probability. Only the latest BETS_LIMIT bets are
read, so very active markets get a shorter history.
"""

import logging
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from pmnews.core.clock import from_unix
from pmnews.sources.base import Category, NormalizedMarket, PricePoint, SourceError
from pmnews.sources.http import PoliteClient

logger = logging.getLogger(__name__)

BASE_URL = "https://api.manifold.markets/v0"
BETS_LIMIT = 1000

TOPICS: dict[Category, tuple[str, ...]] = {
    Category.geopolitics: ("geopolitics", "us-politics"),
    Category.finance: ("finance",),
    Category.tech: ("technology", "ai"),
    Category.culture: ("entertainment",),
}


def normalize_market(raw: dict[str, Any], category: Category) -> NormalizedMarket | None:
    if (
        raw.get("outcomeType") != "BINARY"
        or raw.get("token", "MANA") != "MANA"
        or raw.get("isResolved")
        or raw.get("probability") is None
    ):
        return None
    return NormalizedMarket(
        source="manifold",
        external_id=raw["id"],
        question=raw["question"],
        category=category,
        probability=Decimal(str(raw["probability"])),
        volume=Decimal(str(raw.get("volume") or 0)),
        volume_unit="mana",
        close_time=from_unix(raw["closeTime"] / 1000) if raw.get("closeTime") else None,
        url=raw.get("url"),
        history_ref=raw["id"],
    )


def daily_closes(bets: Iterable[dict[str, Any]], since: date | None) -> list[PricePoint]:
    latest: dict[date, tuple[int, float]] = {}
    for bet in bets:
        if bet.get("isRedemption") or bet.get("isCancelled") or bet.get("probAfter") is None:
            continue
        created = int(bet["createdTime"])
        day = from_unix(created / 1000).date()
        if since and day < since:
            continue
        if day not in latest or created > latest[day][0]:
            latest[day] = (created, float(bet["probAfter"]))
    return [
        PricePoint(day=day, probability=Decimal(str(prob)))
        for day, (_, prob) in sorted(latest.items())
    ]


class ManifoldSource:
    name = "manifold"

    def __init__(self, client: PoliteClient) -> None:
        self._client = client

    async def fetch_markets(self, per_category: int) -> list[NormalizedMarket]:
        seen: set[str] = set()
        result: list[NormalizedMarket] = []
        for category, slugs in TOPICS.items():
            candidates: list[NormalizedMarket] = []
            for slug in slugs:
                try:
                    rows = await self._client.get_json(
                        f"{BASE_URL}/search-markets",
                        endpoint="search-markets",
                        params={
                            "term": "",
                            "filter": "open",
                            "sort": "liquidity",
                            "contractType": "BINARY",
                            "topicSlug": slug,
                            "limit": per_category,
                        },
                    )
                except SourceError as exc:
                    logger.warning("manifold: skipping topic %r: %s", slug, exc)
                    continue
                for raw in rows if isinstance(rows, list) else []:
                    market = normalize_market(raw, category)
                    if market and market.external_id not in seen:
                        seen.add(market.external_id)
                        candidates.append(market)
            candidates.sort(key=lambda m: m.volume, reverse=True)
            result.extend(candidates[:per_category])
        return result

    async def fetch_price_history(
        self, history_ref: str, since: date | None = None
    ) -> list[PricePoint]:
        bets = await self._client.get_json(
            f"{BASE_URL}/bets",
            endpoint="bets",
            params={"contractId": history_ref, "limit": BETS_LIMIT},
        )
        if not isinstance(bets, list):
            raise SourceError("manifold: unexpected /bets response shape")
        return daily_closes(bets, since)
