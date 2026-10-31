import asyncio

import pytest

from pmnews.api import app as app_module
from pmnews.core.config import settings


async def test_startup_does_not_wait_for_the_first_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    release = asyncio.Event()

    async def slow_fetch() -> None:
        await release.wait()  # simulates an unreachable source

    monkeypatch.setattr(app_module, "_scheduled_fetch", slow_fetch)
    monkeypatch.setattr(settings, "SOURCES_ENABLED", ["kalshi"])

    async with asyncio.timeout(2), app_module.lifespan(app_module.app):
        release.set()


async def test_no_fetch_is_scheduled_when_nothing_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SOURCES_ENABLED", [])
    monkeypatch.setattr(settings, "NEWS_ENABLED", False)

    async with app_module.lifespan(app_module.app):
        assert not app_module._scheduler.running
