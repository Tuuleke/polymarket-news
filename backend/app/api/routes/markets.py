from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.market import MarketRead

router = APIRouter()


@router.get("/", response_model=list[MarketRead])
async def get_markets(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # TODO: implement
    raise NotImplementedError


@router.get("/{market_id}", response_model=MarketRead)
async def get_market(market_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: implement
    raise NotImplementedError
