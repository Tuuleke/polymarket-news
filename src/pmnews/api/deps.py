"""Shared FastAPI dependencies. Tests override these via app.dependency_overrides."""

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.core.config import settings
from pmnews.db.database import get_db
from pmnews.llm.articles import LLMService, get_llm_service
from pmnews.sources.polymarket import PolymarketService


@lru_cache
def polymarket_service() -> PolymarketService:
    return PolymarketService()


def get_polymarket() -> PolymarketService:
    if not settings.POLYMARKET_ENABLED:
        raise HTTPException(status_code=503, detail="The Polymarket source is disabled")
    return polymarket_service()


def require_generation_allowed(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Guard for endpoints that make paid LLM calls (see GENERATION_MODE)."""
    if settings.GENERATION_MODE == "open":
        return
    if settings.GENERATION_MODE == "disabled":
        raise HTTPException(status_code=403, detail="Article generation is disabled")
    expected = settings.ADMIN_TOKEN.get_secret_value()
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid admin token")


DbSession = Annotated[AsyncSession, Depends(get_db)]
Llm = Annotated[LLMService, Depends(get_llm_service)]
Polymarket = Annotated[PolymarketService, Depends(get_polymarket)]
