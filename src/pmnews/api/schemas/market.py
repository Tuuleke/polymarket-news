from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from pmnews.api.schemas.article import ArticleRead


class MarketSnapshotRead(BaseModel):
    id: int
    market_id: int
    date: date
    probability: float

    model_config = ConfigDict(from_attributes=True)


class MarketBase(BaseModel):
    source: str
    external_id: str
    event_id: str | None = None
    question: str
    category: str
    probability: float
    volume: float
    volume_unit: str
    end_date: datetime | None = None
    url: str | None = None


class MarketCreate(MarketBase):
    pass


class MarketRead(MarketBase):
    id: int
    fetched_at: datetime
    articles: list[ArticleRead] = []
    snapshots: list[MarketSnapshotRead] = []

    model_config = ConfigDict(from_attributes=True)


class GenerateUpdatesResult(BaseModel):
    generated: int
    dates: list[str]
    snapshots_added: int
