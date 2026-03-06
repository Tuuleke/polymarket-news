from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    polymarket_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String, index=True)
    probability: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="market")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(String)
    probability_at_generation: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    market: Mapped["Market"] = relationship(back_populates="articles")
