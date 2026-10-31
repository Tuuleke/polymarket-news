"""Shared FastAPI dependencies. Tests override these via app.dependency_overrides."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
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


DbSession = Annotated[AsyncSession, Depends(get_db)]
Llm = Annotated[LLMService, Depends(get_llm_service)]
Polymarket = Annotated[PolymarketService, Depends(get_polymarket)]
