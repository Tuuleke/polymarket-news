import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ArticleType(str, enum.Enum):
    explanation = "explanation"
    update = "update"


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    polymarket_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    clob_token_id: Mapped[str | None] = mapped_column(String, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String, index=True)
    probability: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="market")
    snapshots: Mapped[list["MarketSnapshot"]] = relationship(back_populates="market")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (UniqueConstraint("market_id", "date", name="uq_snapshot_market_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    date: Mapped[date] = mapped_column(Date, index=True)
    probability: Mapped[float] = mapped_column(Float)

    market: Mapped["Market"] = relationship(back_populates="snapshots")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(String)
    probability_at_generation: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    article_type: Mapped[ArticleType] = mapped_column(
        Enum(ArticleType, name="article_type_enum"),
        default=ArticleType.explanation,
    )
    probability_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    market: Mapped["Market"] = relationship(back_populates="articles")
