import json
from pathlib import Path

import httpx
import pytest
import respx

from pmnews.sources.base import SourceError
from pmnews.sources.http import PoliteClient
from pmnews.sources.raw_store import LocalRawStore

URL = "https://api.example.test/v1/things"


class RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _client(sleep: RecordingSleep, **kwargs: object) -> PoliteClient:
    return PoliteClient("example", min_interval=0.0, sleep=sleep, **kwargs)  # type: ignore[arg-type]


async def test_retries_on_429_honouring_retry_after(mock_http: respx.MockRouter) -> None:
    mock_http.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    sleep = RecordingSleep()

    assert await _client(sleep).get_json(URL, endpoint="things") == {"ok": True}
    assert sleep.calls and sleep.calls[0] >= 7


async def test_retries_network_errors_with_growing_backoff(mock_http: respx.MockRouter) -> None:
    mock_http.get(URL).mock(
        side_effect=[httpx.ConnectTimeout("t"), httpx.ConnectTimeout("t"), httpx.Response(200)]
    )
    sleep = RecordingSleep()

    await _client(sleep, base_backoff=1.0).get(URL, endpoint="things")

    assert len(sleep.calls) == 2
    assert 1.0 <= sleep.calls[0] < 2.0
    assert 2.0 <= sleep.calls[1] < 3.0


async def test_gives_up_after_max_attempts(mock_http: respx.MockRouter) -> None:
    route = mock_http.get(URL).mock(return_value=httpx.Response(503))

    with pytest.raises(SourceError, match="HTTP 503"):
        await _client(RecordingSleep(), max_attempts=3).get(URL, endpoint="things")
    assert route.call_count == 3


async def test_client_errors_are_not_retried(mock_http: respx.MockRouter) -> None:
    route = mock_http.get(URL).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceError, match="HTTP 404"):
        await _client(RecordingSleep()).get(URL, endpoint="things")
    assert route.call_count == 1


async def test_spaces_requests_by_min_interval(mock_http: respx.MockRouter) -> None:
    mock_http.get(URL).mock(return_value=httpx.Response(200))
    sleep = RecordingSleep()
    client = PoliteClient("example", min_interval=5.0, sleep=sleep)

    await client.get(URL, endpoint="things")
    await client.get(URL, endpoint="things")

    assert len(sleep.calls) == 1
    assert 4.0 < sleep.calls[0] <= 5.0


async def test_conditional_request_reuses_body_on_304(mock_http: respx.MockRouter) -> None:
    route = mock_http.get(URL).mock(
        side_effect=[
            httpx.Response(200, json={"v": 1}, headers={"ETag": '"abc"'}),
            httpx.Response(304),
        ]
    )
    client = _client(RecordingSleep())

    first = await client.get_json(URL, endpoint="things")
    second = await client.get_json(URL, endpoint="things")

    assert first == second == {"v": 1}
    assert route.calls[1].request.headers["If-None-Match"] == '"abc"'


async def test_successful_bodies_land_unchanged_in_the_raw_store(
    mock_http: respx.MockRouter, tmp_path: Path
) -> None:
    body = b'{"exact": "bytes",  "spacing": true}'
    mock_http.get(URL).mock(return_value=httpx.Response(200, content=body))
    client = _client(RecordingSleep(), raw_store=LocalRawStore(tmp_path))

    await client.get(URL, endpoint="things", params={"page": 2})

    [stored] = tmp_path.glob("source=example/dt=*/things/*.body")
    assert stored.read_bytes() == body
    meta = json.loads(stored.with_suffix("").with_suffix(".meta.json").read_text())
    assert meta["params"] == {"page": 2}
    assert meta["status"] == 200
