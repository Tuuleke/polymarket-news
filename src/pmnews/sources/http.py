"""
HTTP client shared by all source adapters, built to be a polite API consumer:

- a minimum interval between requests per source (simple client-side rate limit);
- retries with exponential backoff and jitter on 429, 5xx and network errors,
  honouring the server's Retry-After header;
- conditional requests (ETag / Last-Modified), so unchanged data is not re-downloaded;
- every successful response body is written unchanged to the raw store.
"""

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from pmnews.sources.base import SourceError
from pmnews.sources.raw_store import RawStore

logger = logging.getLogger(__name__)

USER_AGENT = "pmnews/0.2 (+https://github.com/Tuuleke/polymarket-news)"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_SECONDS = 60.0

Params = Mapping[str, str | int]


class PoliteClient:
    def __init__(
        self,
        source: str,
        *,
        min_interval: float,
        raw_store: RawStore | None = None,
        timeout: float = 20.0,
        max_attempts: int = 4,
        base_backoff: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._source = source
        self._min_interval = min_interval
        self._raw_store = raw_store
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._validators: dict[str, tuple[dict[str, str], bytes]] = {}

    async def get_json(self, url: str, *, endpoint: str, params: Params | None = None) -> Any:
        body = await self.get(url, endpoint=endpoint, params=params)
        try:
            return json.loads(body)
        except ValueError as exc:
            raise SourceError(f"{self._source}: {endpoint} returned invalid JSON") from exc

    async def get(self, url: str, *, endpoint: str, params: Params | None = None) -> bytes:
        request_key = str(httpx.URL(url, params=dict(params or {})))
        for attempt in range(1, self._max_attempts + 1):
            headers = (
                dict(self._validators[request_key][0]) if request_key in self._validators else {}
            )
            try:
                await self._wait_turn()
                resp = await self._client.get(url, params=params, headers=headers)
            except httpx.TransportError as exc:
                if attempt == self._max_attempts:
                    raise SourceError(f"{self._source}: {endpoint} unreachable: {exc!r}") from exc
                await self._backoff(attempt, endpoint, repr(exc), retry_after=None)
                continue

            if resp.status_code == 304 and request_key in self._validators:
                return self._validators[request_key][1]
            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_attempts:
                await self._backoff(
                    attempt, endpoint, str(resp.status_code), resp.headers.get("Retry-After")
                )
                continue
            if resp.status_code != 200:
                raise SourceError(f"{self._source}: {endpoint} returned HTTP {resp.status_code}")

            self._remember_validators(request_key, resp)
            await self._store_raw(endpoint, url, params, resp)
            return resp.content
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _wait_turn(self) -> None:
        async with self._lock:
            wait = self._last_request + self._min_interval - time.monotonic()
            if wait > 0:
                await self._sleep(wait)
            self._last_request = time.monotonic()

    async def _backoff(
        self, attempt: int, endpoint: str, reason: str, retry_after: str | None
    ) -> None:
        delay = self._base_backoff * 2 ** (attempt - 1) + random.uniform(0, self._base_backoff)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), MAX_RETRY_AFTER_SECONDS))
        logger.warning(
            "%s: %s failed (%s), retry %d in %.1fs",
            self._source,
            endpoint,
            reason,
            attempt,
            delay,
        )
        await self._sleep(delay)

    def _remember_validators(self, request_key: str, resp: httpx.Response) -> None:
        validators = {}
        if etag := resp.headers.get("ETag"):
            validators["If-None-Match"] = etag
        if last_modified := resp.headers.get("Last-Modified"):
            validators["If-Modified-Since"] = last_modified
        if validators:
            self._validators[request_key] = (validators, resp.content)

    async def _store_raw(
        self, endpoint: str, url: str, params: Params | None, resp: httpx.Response
    ) -> None:
        if self._raw_store is None:
            return
        meta = {
            "source": self._source,
            "url": url,
            "params": dict(params or {}),
            "status": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
        }
        await asyncio.to_thread(self._raw_store.put, self._source, endpoint, resp.content, meta)
