"""
The contract every data source implements.

Each platform has its own API shape, units and quirks. Adapters translate them into
these normalised models so the rest of the system (ingestion, warehouse, API) never
needs to know which platform a market came from — only the `source` column does.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Category(StrEnum):
    """The four tabs the UI shows. Adapters map platform categories onto these."""

    geopolitics = "geopolitics"
    finance = "finance"
    culture = "culture"
    tech = "tech"


VolumeUnit = Literal["usd", "contracts", "mana"]
Probability = Decimal


class NormalizedMarket(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    external_id: str
    event_id: str | None = None
    question: str
    category: Category
    probability: Probability = Field(ge=0, le=1)
    # Volume is not comparable across platforms: USD on Polymarket, contracts traded
    # on Kalshi, play-money "mana" on Manifold. The unit travels with the number.
    volume: Decimal = Field(ge=0)
    volume_unit: VolumeUnit
    close_time: AwareDatetime | None = None
    url: str | None = None
    # Opaque handle the same adapter needs later to fetch price history (None if unavailable).
    history_ref: str | None


class PricePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    day: date
    probability: Probability = Field(ge=0, le=1)


class NewsItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    url: str
    title: str
    author: str | None = None
    published_at: AwareDatetime | None = None
    summary: str = ""


class SourceError(Exception):
    """A source could not be reached or returned something unusable."""


class MarketSource(Protocol):
    name: str

    async def fetch_markets(self, per_category: int) -> list[NormalizedMarket]:
        """Return up to `per_category` of the most traded open markets for each Category."""
        ...

    async def fetch_price_history(
        self, history_ref: str, since: date | None = None
    ) -> list[PricePoint]:
        """Return one probability per day, oldest first, from `since` (inclusive) if given."""
        ...
