import httpx
import pytest
import respx
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.core.config import Settings, settings
from pmnews.db.models import Market


async def _market_id(db: AsyncSession) -> int:
    market = Market(polymarket_id="1", question="Q?", category="tech", probability=0.5, volume=1.0)
    db.add(market)
    await db.commit()
    return market.id


async def test_generation_is_disabled_by_default(
    client: httpx.AsyncClient, db: AsyncSession, openrouter: respx.Route
) -> None:
    assert Settings.model_fields["GENERATION_MODE"].default == "disabled"
    market_id = await _market_id(db)

    resp = await client.post(f"/api/v1/markets/{market_id}/explain")

    assert resp.status_code == 403
    assert openrouter.call_count == 0


@pytest.mark.parametrize(("header", "status"), [(None, 401), ("wrong", 401), ("s3cret", 201)])
async def test_token_mode_requires_the_admin_token(
    client: httpx.AsyncClient,
    db: AsyncSession,
    openrouter: respx.Route,
    monkeypatch: pytest.MonkeyPatch,
    header: str | None,
    status: int,
) -> None:
    monkeypatch.setattr(settings, "GENERATION_MODE", "token")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", SecretStr("s3cret"))
    market_id = await _market_id(db)
    headers = {"X-Admin-Token": header} if header else {}

    resp = await client.post(f"/api/v1/markets/{market_id}/explain", headers=headers)

    assert resp.status_code == status
    assert openrouter.call_count == (1 if status == 201 else 0)


def test_token_mode_without_a_token_is_a_configuration_error() -> None:
    with pytest.raises(ValidationError, match="requires ADMIN_TOKEN"):
        Settings(GENERATION_MODE="token", ADMIN_TOKEN=SecretStr(""), _env_file=None)
