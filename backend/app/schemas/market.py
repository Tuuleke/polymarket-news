from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
