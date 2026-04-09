from datetime import date, datetime

from pydantic import BaseModel


class ArticleBase(BaseModel):
    title: str
    body: str
    llm_model: str
    probability_at_generation: float
    article_type: str = "explanation"
    probability_change: float | None = None
    snapshot_date: date | None = None


class ArticleCreate(ArticleBase):
    market_id: int


class ArticleRead(ArticleBase):
    id: int
    market_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
