"""
Shared fixtures.

Database tests run against a real Postgres (the same pgvector image as docker compose)
started once per test session with testcontainers, because the app relies on
Postgres-only features such as ON CONFLICT. Every test starts from empty tables.
"""

import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from alembic import command
from alembic.config import Config
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

from pmnews.api.app import app
from pmnews.api.deps import get_llm, get_sources
from pmnews.core.config import settings
from pmnews.db.database import Base, get_db
from pmnews.llm.articles import LLMService
from pmnews.sources.http import PoliteClient
from pmnews.sources.polymarket import PolymarketSource

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
OPENROUTER_TEST_URL = "https://openrouter.test/api/v1"


def load_fixture(relative_path: str) -> Any:
    return json.loads((FIXTURES / relative_path).read_text())


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Start Postgres once and build the schema with the real migrations, not create_all."""
    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as pg:
        url = pg.get_connection_url()
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture(scope="session")
async def engine(postgres_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(postgres_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def generation_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GENERATION_MODE", "open")


@pytest.fixture
def mock_http() -> Iterator[respx.MockRouter]:
    """Every outgoing HTTP request must match a registered route, or the test fails."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture
def llm() -> LLMService:
    # The OpenAI SDK defaults to its own httpx2 transport, which respx cannot intercept;
    # passing a standard httpx client keeps every request inside the respx mock.
    client = AsyncOpenAI(
        api_key="test-key",
        base_url=OPENROUTER_TEST_URL,
        max_retries=0,
        http_client=httpx.AsyncClient(),  # type: ignore[arg-type]  # accepted at runtime
    )
    return LLMService(client, model="deepseek/deepseek-v3.2", web_search=False)


@pytest.fixture
def openrouter(mock_http: respx.MockRouter) -> respx.Route:
    return mock_http.post(f"{OPENROUTER_TEST_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=load_fixture("openrouter/chat_completion.json"))
    )


@pytest.fixture
def polymarket() -> PolymarketSource:
    # Real adapter against respx-mocked endpoints; one attempt so error tests do not wait.
    return PolymarketSource(PoliteClient("polymarket", min_interval=0.0, max_attempts=1))


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMService,
    polymarket: PolymarketSource,
) -> AsyncIterator[httpx.AsyncClient]:
    """API client wired to the test database and test doubles. Lifespan (scheduler) is not run."""

    async def _get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_sources] = lambda: {"polymarket": polymarket}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
