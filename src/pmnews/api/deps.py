"""Shared FastAPI dependencies. Tests override these via app.dependency_overrides."""

import secrets
from collections.abc import Mapping
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.core.config import settings
from pmnews.db.database import get_db
from pmnews.llm.articles import LLMService, get_llm_service
from pmnews.sources.base import MarketSource
from pmnews.sources.registry import build_sources

MAX_PAGE_SIZE = 100


@lru_cache
def get_sources() -> Mapping[str, MarketSource]:
    """The enabled market sources, built once from SOURCES_ENABLED."""
    return build_sources(settings)


def get_llm() -> LLMService:
    if not settings.OPENROUTER_API_KEY.get_secret_value():
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured")
    return get_llm_service()


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
Llm = Annotated[LLMService, Depends(get_llm)]
Sources = Annotated[Mapping[str, MarketSource], Depends(get_sources)]
