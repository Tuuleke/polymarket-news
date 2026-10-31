import asyncio
import itertools
import logging
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from pmnews.api.deps import (
    MAX_PAGE_SIZE,
    DbSession,
    Llm,
    Sources,
    require_generation_allowed,
)
from pmnews.api.schemas.article import ArticleRead
from pmnews.api.schemas.market import GenerateUpdatesResult, MarketRead
from pmnews.core.config import settings
from pmnews.db.models import Article, ArticleType, Market, MarketSnapshot
from pmnews.llm.articles import ArticleFields
from pmnews.sources.base import SourceError

logger = logging.getLogger(__name__)
router = APIRouter()

THRESHOLD = 0.10  # 10 percentage point move
SNAPSHOT_WINDOW_DAYS = 90
LLM_CONCURRENCY = 5


def find_significant_moves(
    snapshots: Sequence[MarketSnapshot],
    already_covered: set[date],
    threshold: float = THRESHOLD,
) -> list[tuple[MarketSnapshot, MarketSnapshot]]:
    """
    Return (prev, curr) pairs of consecutive snapshots at most 2 days apart whose
    probability moved by more than `threshold`, skipping dates that already have an article.
    """
    moves = []
    for prev, curr in itertools.pairwise(snapshots):
        if curr.date in already_covered or curr.date - prev.date > timedelta(days=2):
            continue
        if abs(curr.probability - prev.probability) > threshold:
            moves.append((prev, curr))
    return moves


async def _get_market_or_404(db: DbSession, market_id: int) -> Market:
    market = await db.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


def _recent_snapshots() -> LoaderOption:
    """
    Load only the last SNAPSHOT_WINDOW_DAYS of each market's history, counted back from
    that market's latest snapshot so markets that stopped trading still show a chart.
    """
    newer = aliased(MarketSnapshot)
    latest = (
        select(func.max(newer.date)).where(newer.market_id == MarketSnapshot.market_id)
    ).scalar_subquery()
    window = literal(timedelta(days=SNAPSHOT_WINDOW_DAYS))
    return selectinload(Market.snapshots.and_(MarketSnapshot.date >= latest - window))


@router.get("/", response_model=list[MarketRead])
async def get_markets(
    db: DbSession,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Market]:
    stmt = (
        select(Market)
        .options(selectinload(Market.articles), _recent_snapshots())
        .order_by(Market.volume.desc(), Market.id)
        .offset(offset)
        .limit(limit)
    )
    if category:
        stmt = stmt.where(Market.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{market_id}", response_model=MarketRead)
async def get_market(market_id: int, db: DbSession) -> Market:
    result = await db.execute(
        select(Market)
        .options(selectinload(Market.articles), _recent_snapshots())
        .where(Market.id == market_id)
    )
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.post(
    "/{market_id}/explain",
    status_code=201,
    response_model=ArticleRead,
    dependencies=[Depends(require_generation_allowed)],
)
async def generate_explanation(market_id: int, db: DbSession, llm: Llm) -> Article:
    """
    Generate the explanation article for a market, replacing the existing one if present.
    Each call makes one paid LLM request.
    """
    market = await _get_market_or_404(db, market_id)

    existing_result = await db.execute(
        select(Article).where(
            Article.market_id == market_id,
            Article.article_type == ArticleType.explanation,
        )
    )
    existing = existing_result.scalar_one_or_none()

    article_data = await llm.generate_explanation(market)

    if existing:
        for key, value in article_data.items():
            setattr(existing, key, value)
        await db.commit()
        await db.refresh(existing)
        return existing

    article = Article(market_id=market.id, **article_data)
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


@router.post(
    "/{market_id}/generate-updates",
    status_code=201,
    dependencies=[Depends(require_generation_allowed)],
)
async def generate_updates(
    market_id: int, db: DbSession, llm: Llm, sources: Sources
) -> GenerateUpdatesResult:
    """
    Scan all daily snapshots for this market.
    For each consecutive pair where abs(probability delta) > 10pp and no article exists
    for that date, generate an update article.
    Only triggered by a user button click, never called automatically.
    """
    market = await _get_market_or_404(db, market_id)

    source = sources.get(market.source)
    if source is None:
        raise HTTPException(status_code=503, detail=f"The {market.source} source is disabled")
    if not market.history_ref:
        raise HTTPException(status_code=422, detail="This market has no price history reference")

    # Backfill daily history from the source (safe to re-run; existing dates are skipped).
    last_snap_date = (
        await db.execute(
            select(MarketSnapshot.date)
            .where(MarketSnapshot.market_id == market_id)
            .order_by(MarketSnapshot.date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    try:
        history = await source.fetch_price_history(market.history_ref, since=last_snap_date)
    except SourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    logger.info(
        "generate-updates: market_id=%d source=%s since=%s got %d points",
        market_id,
        market.source,
        last_snap_date,
        len(history),
    )

    inserted = 0
    snapshot_values = [
        {"market_id": market_id, "date": p.day, "probability": float(p.probability)}
        for p in history
    ]
    if snapshot_values:
        result = await db.execute(
            pg_insert(MarketSnapshot)
            .values(snapshot_values)
            .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
            .returning(MarketSnapshot.id)
        )
        inserted = len(result.all())
        await db.commit()
    logger.info("generate-updates: inserted %d new snapshots", inserted)

    snapshots = (
        (
            await db.execute(
                select(MarketSnapshot)
                .where(MarketSnapshot.market_id == market_id)
                .order_by(MarketSnapshot.date.asc())
            )
        )
        .scalars()
        .all()
    )

    existing_dates = set(
        (
            await db.execute(
                select(Article.snapshot_date).where(
                    Article.market_id == market_id,
                    Article.article_type == ArticleType.update,
                    Article.snapshot_date.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    all_moves = find_significant_moves(snapshots, {d for d in existing_dates if d is not None})
    # Full history can contain dozens of moves; only the most recent ones are written per request.
    moves = all_moves[-settings.MAX_UPDATES_PER_REQUEST :]
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

    async def generate_with_semaphore(prev: MarketSnapshot, curr: MarketSnapshot) -> ArticleFields:
        async with semaphore:
            return await llm.generate_update(market, prev, curr)

    results = await asyncio.gather(*(generate_with_semaphore(p, c) for p, c in moves))
    created = []
    for (_, curr), article_data in zip(moves, results, strict=True):
        db.add(Article(market_id=market.id, **article_data))
        created.append(str(curr.date))

    logger.info(
        "generate-updates: found %d significant moves, generated %d articles",
        len(all_moves),
        len(created),
    )
    if created:
        await db.commit()

    return GenerateUpdatesResult(generated=len(created), dates=created, snapshots_added=inserted)
