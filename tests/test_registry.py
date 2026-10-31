from pathlib import Path

import pytest
from pydantic import ValidationError

from pmnews.core.config import Settings
from pmnews.sources.kalshi import KalshiSource
from pmnews.sources.manifold import ManifoldSource
from pmnews.sources.polymarket import PolymarketSource
from pmnews.sources.registry import build_sources


def _settings(sources: str) -> Settings:
    return Settings(_env_file=None, SOURCES_ENABLED=sources)


def test_defaults_are_kalshi_and_manifold_without_polymarket() -> None:
    assert Settings.model_fields["SOURCES_ENABLED"].default == ["kalshi", "manifold"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("kalshi,manifold", {"kalshi": KalshiSource, "manifold": ManifoldSource}),
        ("manifold", {"manifold": ManifoldSource}),
        (" Kalshi , polymarket ", {"kalshi": KalshiSource, "polymarket": PolymarketSource}),
        ("", {}),
    ],
)
def test_switching_sources_is_a_config_change(
    value: str, expected: dict[str, type], tmp_path: Path
) -> None:
    sources = build_sources(_settings(value).model_copy(update={"RAW_DATA_DIR": tmp_path}))

    assert {name: type(src) for name, src in sources.items()} == expected


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown sources"):
        _settings("kalshi,predictit")
