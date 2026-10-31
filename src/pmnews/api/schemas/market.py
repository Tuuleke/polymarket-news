from datetime import date, datetime

from pydantic import BaseModel

from pmnews.api.schemas.article import ArticleRead


class MarketSnapshotRead(BaseModel):
    id: int
    market_id: int
    date: date
    probability: float

    model_config = {"from_attributes": True}


class MarketBase(BaseModel):
    polymarket_id: str
    question: str
    category: str
    probability: float
    volume: float
    end_date: datetime | None = None


class MarketCreate(MarketBase):
    pass


class MarketRead(MarketBase):
    id: int
    fetched_at: datetime
    articles: list[ArticleRead] = []
    snapshots: list[MarketSnapshotRead] = []

    model_config = {"from_attributes": True}
