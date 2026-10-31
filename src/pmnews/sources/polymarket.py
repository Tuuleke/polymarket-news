"""
Service for fetching data from the Polymarket Gamma and CLOB APIs.
"""

from datetime import UTC, date, datetime, time
from typing import Any, ClassVar

import httpx

from pmnews.core.config import settings

RawMarket = dict[str, Any]


class PolymarketService:
    """Fetches and normalises market data from Polymarket APIs."""

    # Polymarket tag IDs for our four categories (discovered via API exploration)
    TAG_IDS: ClassVar[dict[str, str]] = {
        "geopolitics": "2",  # Politics
        "finance": "120",  # Finance
        "culture": "596",  # Culture
        "tech": "439",  # AI / Tech
    }

    def __init__(
        self,
        gamma_base: str = settings.POLYMARKET_GAMMA_API_URL,
        clob_base: str = settings.POLYMARKET_CLOB_API_URL,
    ) -> None:
        self._gamma_base = gamma_base
        self._clob_base = clob_base

    async def fetch_markets_by_tag(self, tag: str, limit: int = 10) -> list[RawMarket]:
        """Fetch top markets by volume for a given tag from the Gamma API using tag_id."""
        tag_id = self.TAG_IDS.get(tag)
        if not tag_id:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._gamma_base}/markets",
                params={
                    "tag_id": tag_id,
                    "order": "volume",
                    "ascending": "false",
                    "limit": limit,
                    "active": "true",
                    "closed": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data if isinstance(data, list) else []

    async def fetch_price_history(
        self, clob_token_id: str, since: date | None = None
    ) -> list[dict[str, float]]:
        """
        Fetch daily price history from the CLOB API using the YES token ID.
        Returns a list of dicts with 't' (Unix seconds) and 'p' (probability 0-1) keys.
        Falls back to empty list if CLOB is unavailable.
        If 'since' is provided, only returns data from that date onwards.
        """
        params: dict[str, str | int] = {
            "market": clob_token_id,
            "interval": "max",
            "fidelity": 1440,
        }
        if since:
            # Midnight UTC; strftime("%s") is a non-portable glibc extension in local time.
            params["since"] = int(datetime.combine(since, time.min, tzinfo=UTC).timestamp())
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(f"{self._clob_base}/prices-history", params=params)
                resp.raise_for_status()
                history: list[dict[str, float]] = resp.json().get("history", [])
            except httpx.HTTPError:
                return []
        return history
