"""Scheduled ingestion of news feeds into news_items (upserted by canonical URL)."""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.core.clock import utc_now
from pmnews.db.models import NewsItem
from pmnews.sources.base import SourceError
from pmnews.sources.rss import RssSource

logger = logging.getLogger(__name__)


async def ingest_news(session_factory: async_sessionmaker[AsyncSession], rss: RssSource) -> int:
    """Fetch each feed independently; a failing feed is logged and skipped."""
    stored = 0
    for feed in rss.feeds:
        try:
            items = await rss.fetch_feed(feed)
        except SourceError as exc:
            logger.error("ingest: feed %s failed: %s", feed.name, exc)
            continue
        async with session_factory() as session:
            for item in items:
                values = item.model_dump() | {"fetched_at": utc_now()}
                await session.execute(
                    pg_insert(NewsItem)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["url"],
                        set_={k: v for k, v in values.items() if k != "url"},
                    )
                )
            await session.commit()
        stored += len(items)
        logger.info("ingest: feed %s stored %d items", feed.name, len(items))
    return stored
