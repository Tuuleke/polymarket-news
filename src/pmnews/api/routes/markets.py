import asyncio
import itertools
import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from pmnews.api.deps import DbSession, Llm, Polymarket, require_generation_allowed
from pmnews.api.schemas.article import ArticleRead
from pmnews.api.schemas.market import GenerateUpdatesResult, MarketRead
from pmnews.db.models import Article, ArticleType, Market, MarketSnapshot
from pmnews.llm.articles import ArticleFields

logger = logging.getLogger(__name__)
router = APIRouter()

THRESHOLD = 0.10  # 10 percentage point move
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


@router.get("/", response_model=list[MarketRead])
async def get_markets(db: DbSession, category: str | None = None) -> Sequence[Market]:
    stmt = (
        select(Market)
        .options(selectinload(Market.articles), selectinload(Market.snapshots))
        .order_by(Market.volume.desc())
    )
    if category:
        stmt = stmt.where(Market.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{market_id}", response_model=MarketRead)
async def get_market(market_id: int, db: DbSession) -> Market:
    result = await db.execute(
        select(Market)
        .options(selectinload(Market.articles), selectinload(Market.snapshots))
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
    Generate the evergreen explanation article for a market.
    Returns 409 if one already exists (idempotent — safe to check before pressing).
    Only triggered by a user button click, never called automatically.
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
    market_id: int, db: DbSession, llm: Llm, polymarket: Polymarket
) -> GenerateUpdatesResult:
    """
    Scan all daily snapshots for this market.
    For each consecutive pair where abs(probability delta) > 10pp and no article exists
    for that date, generate an update article.
    Only triggered by a user button click, never called automatically.
    """
    market = await _get_market_or_404(db, market_id)

    # Backfill historical price snapshots from CLOB API (safe to re-run; skips existing dates)
    if not market.clob_token_id:
        raise HTTPException(
            status_code=422, detail="Market has no CLOB token ID — cannot fetch price history"
        )

    # Find the last snapshot date to only fetch new data
    last_snap_date = (
        await db.execute(
            select(MarketSnapshot.date)
            .where(MarketSnapshot.market_id == market_id)
            .order_by(MarketSnapshot.date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    logger.info(
        "generate-updates: market_id=%d clob_token_id=%s last_snap_date=%s",
        market_id,
        market.clob_token_id,
        last_snap_date,
    )

    history = await polymarket.fetch_price_history(market.clob_token_id, since=last_snap_date)
    logger.info("generate-updates: got %d history points from CLOB", len(history))

    inserted = 0
    snapshot_values = []
    for point in history:
        try:
            ts = point["t"]
            if ts > 1e10:
                ts = ts / 1000
            snap_date = datetime.fromtimestamp(ts, UTC).date()
            prob = float(point["p"])
        except (KeyError, ValueError, TypeError, OSError) as e:
            logger.warning("generate-updates: skipping point %s — %s", point, e)
            continue
        snapshot_values.append({"market_id": market_id, "date": snap_date, "probability": prob})

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

    moves = find_significant_moves(snapshots, {d for d in existing_dates if d is not None})
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
        len(moves),
        len(created),
    )
    if created:
        await db.commit()

    return GenerateUpdatesResult(generated=len(created), dates=created, snapshots_added=inserted)
