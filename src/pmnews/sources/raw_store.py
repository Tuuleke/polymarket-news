"""
Landing zone for raw API responses.

Every successful response body is written unchanged, partitioned by source and UTC date
(`source=kalshi/dt=2026-10-31/events/...`), so downstream models can be rebuilt without
calling the APIs again. This local version writes to disk; Phase 3 adds an S3 version
behind the same interface.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from pmnews.core.clock import utc_now


class RawStore(Protocol):
    def put(self, source: str, endpoint: str, body: bytes, meta: dict[str, Any]) -> str:
        """Store one response body and its request metadata; return the object key."""
        ...


class LocalRawStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def put(self, source: str, endpoint: str, body: bytes, meta: dict[str, Any]) -> str:
        fetched_at = utc_now()
        digest = hashlib.sha256(body).hexdigest()[:12]
        key = (
            f"source={source}/dt={fetched_at.date().isoformat()}/{endpoint}/"
            f"{fetched_at:%H%M%S}-{digest}"
        )
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".body").write_bytes(body)
        path.with_suffix(".meta.json").write_text(
            json.dumps({**meta, "fetched_at": fetched_at.isoformat()}, indent=2)
        )
        return key
