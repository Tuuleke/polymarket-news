"""
RSS/Atom news source. Only title, link, author, publication time and the feed's own
summary are kept, unchanged apart from removing HTML markup.

Feeds are limited to publishers whose terms allow reuse (checked 2026-10-31; see
docs/data-sources.md). BBC News was considered and rejected: its terms forbid
extracting metadata from its RSS feeds.
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import feedparser

from pmnews.sources.base import NewsItem, SourceError
from pmnews.sources.http import PoliteClient


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    attribution: str


FEEDS = (
    # Articles under CC BY-ND 4.0: reuse allowed unedited, crediting author and publisher.
    Feed(
        "conversation-global",
        "https://theconversation.com/global/articles.atom",
        "The Conversation (CC BY-ND 4.0)",
    ),
    # US federal government work: public domain, cite the Board as the source.
    Feed(
        "federal-reserve",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "Board of Governors of the Federal Reserve System",
    ),
)

_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _plain_text(value: str) -> str:
    return _SPACE.sub(" ", html.unescape(_TAGS.sub(" ", value))).strip()


def _canonical_url(link: str) -> str:
    """Drop query strings and fragments (tracking parameters) so one article has one URL."""
    parts = urlsplit(link)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _published(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    year, month, day, hour, minute, second = parsed[:6]  # feedparser normalises to UTC
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def parse_feed(feed: Feed, body: bytes) -> list[NewsItem]:
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        raise SourceError(f"rss: {feed.name} is not a valid feed")
    items = []
    for entry in parsed.entries:
        title, link = _plain_text(entry.get("title", "")), entry.get("link")
        if not title or not link:
            continue
        items.append(
            NewsItem(
                source=feed.name,
                url=_canonical_url(link),
                title=title,
                author=_plain_text(entry["author"]) if entry.get("author") else None,
                published_at=_published(entry),
                summary=_plain_text(entry.get("summary", "")),
            )
        )
    return items


class RssSource:
    name = "rss"

    def __init__(self, client: PoliteClient, feeds: tuple[Feed, ...] = FEEDS) -> None:
        self._client = client
        self.feeds = feeds

    async def fetch_feed(self, feed: Feed) -> list[NewsItem]:
        body = await self._client.get(feed.url, endpoint=feed.name)
        return parse_feed(feed, body)
