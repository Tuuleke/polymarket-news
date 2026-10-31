"""
Service for fetching data from the Polymarket Gamma and CLOB APIs.
"""

from datetime import date

import httpx

from pmnews.core.config import settings


class PolymarketService:
    """Fetches and normalises market data from Polymarket APIs."""

    def __init__(self):
        self._gamma_base = settings.POLYMARKET_GAMMA_API_URL
        self._clob_base = settings.POLYMARKET_CLOB_API_URL

    # Polymarket tag IDs for our four categories (discovered via API exploration)
    TAG_IDS: dict[str, str] = {
        "geopolitics": "2",  # Politics
        "finance": "120",  # Finance
        "culture": "596",  # Culture
        "tech": "439",  # AI / Tech
    }

    async def fetch_markets_by_tag(self, tag: str, limit: int = 10) -> list[dict]:
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

    async def fetch_market_by_id(self, polymarket_id: str) -> dict:
        """Fetch a single market by its Polymarket ID."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self._gamma_base}/markets/{polymarket_id}")
            resp.raise_for_status()
            return resp.json()

    async def fetch_price_history(
        self, clob_token_id: str, since: date | None = None
    ) -> list[dict]:
        """
        Fetch daily price history from the CLOB API using the YES token ID.
        Returns a list of dicts with 't' (Unix seconds) and 'p' (probability 0-1) keys.
        Falls back to empty list if CLOB is unavailable.
        If 'since' is provided, only returns data from that date onwards.
        """
        params = {"market": clob_token_id, "interval": "max", "fidelity": 1440}
        if since:
            params["since"] = int(since.strftime("%s"))
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{self._clob_base}/prices-history",
                    params=params,
                )
                resp.raise_for_status()
                return resp.json().get("history", [])
            except httpx.HTTPError:
                return []
