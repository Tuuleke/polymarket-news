"""Shared FastAPI dependencies. Tests override these via app.dependency_overrides."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.db.database import get_db
from pmnews.llm.articles import LLMService, get_llm_service
from pmnews.sources.polymarket import PolymarketService


@lru_cache
def get_polymarket() -> PolymarketService:
    return PolymarketService()


DbSession = Annotated[AsyncSession, Depends(get_db)]
Llm = Annotated[LLMService, Depends(get_llm_service)]
Polymarket = Annotated[PolymarketService, Depends(get_polymarket)]
