import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pmnews.db.database import get_db
from pmnews.db.models import Article, Market, MarketSnapshot
from pmnews.api.schemas.article import ArticleRead
from pmnews.api.schemas.market import MarketRead
from pmnews.llm.articles import LLMService
from pmnews.sources.polymarket import PolymarketService

router = APIRouter()

_llm = LLMService()
_polymarket = PolymarketService()

THRESHOLD = 0.10  # 10 percentage point move


@router.get("/", response_model=list[MarketRead])
async def get_markets(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
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
async def get_market(market_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Market)
        .options(selectinload(Market.articles), selectinload(Market.snapshots))
        .where(Market.id == market_id)
    )
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.post("/{market_id}/explain", status_code=201, response_model=ArticleRead)
async def generate_explanation(market_id: int, db: AsyncSession = Depends(get_db)):
    """
    Generate the evergreen explanation article for a market.
    Returns 409 if one already exists (idempotent — safe to check before pressing).
    Only triggered by a user button click, never called automatically.
    """
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    existing_result = await db.execute(
        select(Article).where(
            Article.market_id == market_id,
            Article.article_type == "explanation",
        )
    )
    existing = existing_result.scalar_one_or_none()

    article_data = await _llm.generate_explanation(market)

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


@router.post("/{market_id}/generate-updates", status_code=201)
async def generate_updates(market_id: int, db: AsyncSession = Depends(get_db)):
    """
    Scan all daily snapshots for this market.
    For each consecutive pair where abs(probability delta) > 10pp and no article exists
    for that date, generate an update article.
    Only triggered by a user button click, never called automatically.
    """
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    # Backfill historical price snapshots from CLOB API (safe to re-run; skips existing dates)
    if not market.clob_token_id:
        raise HTTPException(status_code=422, detail="Market has no CLOB token ID — cannot fetch price history")
    
    # Find the last snapshot date to only fetch new data
    last_snap_result = await db.execute(
        select(MarketSnapshot.date)
        .where(MarketSnapshot.market_id == market_id)
        .order_by(MarketSnapshot.date.desc())
        .limit(1)
    )
    last_snap_date = last_snap_result.scalar_one_or_none()
    logger.info("generate-updates: market_id=%d clob_token_id=%s last_snap_date=%s", 
                market_id, market.clob_token_id, last_snap_date)
    
    history = await _polymarket.fetch_price_history(market.clob_token_id, since=last_snap_date)
    logger.info("generate-updates: got %d history points from CLOB", len(history))
    if history:
        logger.info("generate-updates: first point sample: %s", history[0])

    # Batch insert all snapshots
    inserted = 0
    if history:
        snapshot_values = []
        for point in history:
            try:
                ts = point["t"]
                if ts > 1e10:
                    ts = ts / 1000
                snap_date = date.fromtimestamp(ts)
                prob = float(point["p"])
            except (KeyError, ValueError, TypeError, OSError) as e:
                logger.warning("generate-updates: skipping point %s — %s", point, e)
                continue
            snapshot_values.append({"market_id": market_id, "date": snap_date, "probability": prob})
        
        if snapshot_values:
            await db.execute(
                pg_insert(MarketSnapshot)
                .values(snapshot_values)
                .on_conflict_do_nothing(constraint="uq_snapshot_market_date")
            )
            inserted = len(snapshot_values)
            await db.commit()
    logger.info("generate-updates: inserted/attempted %d snapshots", inserted)

    snap_result = await db.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.market_id == market_id)
        .order_by(MarketSnapshot.date.asc())
    )
    snapshots = snap_result.scalars().all()
    logger.info("generate-updates: total snapshots in DB: %d", len(snapshots))

    existing_result = await db.execute(
        select(Article.snapshot_date).where(
            Article.market_id == market_id,
            Article.article_type == "update",
            Article.snapshot_date.is_not(None),
        )
    )
    existing_dates = {row[0] for row in existing_result.all()}

    created = []
    significant = 0
    tasks = []
    semaphore = asyncio.Semaphore(5)
    
    async def generate_with_semaphore(prev, curr):
        async with semaphore:
            return await _llm.generate_update(market, prev, curr)
    
    for i in range(1, len(snapshots)):
        curr = snapshots[i]
        if curr.date in existing_dates:
            continue
        candidate = snapshots[i - 1]
        prev = candidate if (curr.date - candidate.date) <= timedelta(days=2) else None
        if prev is None:
            continue
        delta = abs(curr.probability - prev.probability)
        if delta > THRESHOLD:
            significant += 1
            logger.info("generate-updates: significant move on %s: %.1f%% → %.1f%% (Δ%.1f%%)",
                        curr.date, prev.probability * 100, curr.probability * 100, delta * 100)
            tasks.append((curr, generate_with_semaphore(prev, curr)))
    
    if tasks:
        results = await asyncio.gather(*[t[1] for t in tasks])
        for (curr, _), article_data in zip(tasks, results):
            db.add(Article(market_id=market.id, **article_data))
            created.append(str(curr.date))
    
    logger.info("generate-updates: found %d significant moves, generated %d articles", significant, len(created))

    if created:
        await db.commit()

    return {"generated": len(created), "dates": created}
