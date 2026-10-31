from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pmnews.db.models import NewsItem
from pmnews.ingestion.news import ingest_news
from pmnews.sources.base import SourceError
from pmnews.sources.http import PoliteClient
from pmnews.sources.rss import FEEDS, Feed, RssSource, parse_feed

FIXTURES = Path(__file__).parent / "fixtures" / "rss"
CONVERSATION, FED = FEEDS


def test_parses_atom_with_author_and_utc_time() -> None:
    items = parse_feed(CONVERSATION, (FIXTURES / "conversation_global.atom").read_bytes())

    assert len(items) == 3
    first = items[0]
    assert first.source == "conversation-global"
    assert first.title.startswith("How the Sphinx is helping")
    assert first.author == "Philip Mannion, Professor of Palaeobiology, UCL"
    assert first.published_at == datetime(2026, 10, 30, 11, 33, 54, tzinfo=UTC)
    assert "<" not in first.summary


def test_parses_rss_and_canonicalises_urls() -> None:
    items = parse_feed(FED, (FIXTURES / "federal_reserve.xml").read_bytes())

    assert [i.title for i in items][1] == "Federal Reserve issues FOMC statement"
    assert all("?" not in i.url and "#" not in i.url for i in items)
    assert items[0].published_at == datetime(2026, 10, 29, 20, 30, tzinfo=UTC)


def test_invalid_feed_raises_source_error() -> None:
    with pytest.raises(SourceError, match="not a valid feed"):
        parse_feed(FED, b"<html>maintenance</html")


async def test_ingest_upserts_by_url_and_skips_failing_feeds(
    mock_http: respx.MockRouter,
    session_factory: async_sessionmaker[AsyncSession],
    db: AsyncSession,
) -> None:
    mock_http.get(CONVERSATION.url).mock(
        return_value=httpx.Response(
            200, content=(FIXTURES / "conversation_global.atom").read_bytes()
        )
    )
    broken = Feed("broken", "https://feeds.example.test/broken.xml", "Example")
    mock_http.get(broken.url).mock(return_value=httpx.Response(404))
    rss = RssSource(PoliteClient("rss", min_interval=0.0, max_attempts=1), (CONVERSATION, broken))

    first = await ingest_news(session_factory, rss)
    second = await ingest_news(session_factory, rss)

    assert first == second == 3
    assert await db.scalar(select(func.count()).select_from(NewsItem)) == 3
