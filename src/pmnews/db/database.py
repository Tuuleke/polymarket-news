from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from pmnews.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
