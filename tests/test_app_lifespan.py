import asyncio

import pytest

from pmnews.api import app as app_module
from pmnews.core.config import settings


async def test_startup_does_not_wait_for_the_first_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    release = asyncio.Event()

    async def slow_fetch() -> None:
        await release.wait()  # simulates an unreachable source

    monkeypatch.setattr(app_module, "_scheduled_fetch", slow_fetch)
    monkeypatch.setattr(settings, "DISABLE_SCHEDULER", False)

    async with asyncio.timeout(2), app_module.lifespan(app_module.app):
        release.set()
