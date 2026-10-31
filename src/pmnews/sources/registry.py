"""Builds the enabled sources from settings. Switching sources is a SOURCES_ENABLED change."""

from collections.abc import Callable

from pmnews.core.config import Settings
from pmnews.sources.base import MarketSource
from pmnews.sources.http import PoliteClient
from pmnews.sources.kalshi import KalshiSource
from pmnews.sources.manifold import ManifoldSource
from pmnews.sources.polymarket import PolymarketSource
from pmnews.sources.raw_store import LocalRawStore, RawStore

# Minimum seconds between requests, kept well below each platform's published limits.
_MIN_INTERVAL = {"kalshi": 0.1, "manifold": 0.15, "polymarket": 0.2}


def _factories(settings: Settings) -> dict[str, Callable[[PoliteClient], MarketSource]]:
    return {
        "kalshi": lambda c: KalshiSource(c, max_pages=settings.KALSHI_MAX_PAGES),
        "manifold": ManifoldSource,
        "polymarket": PolymarketSource,
    }


def build_sources(settings: Settings, raw_store: RawStore | None = None) -> dict[str, MarketSource]:
    store = raw_store or LocalRawStore(settings.RAW_DATA_DIR)
    factories = _factories(settings)
    return {
        name: factories[name](PoliteClient(name, min_interval=_MIN_INTERVAL[name], raw_store=store))
        for name in settings.SOURCES_ENABLED
    }
