from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    config.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10,
    connect_args={"server_settings": {"statement_timeout": "30000", "lock_timeout": "5000"}},
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    # A dependency never commits for the service, and never shares an auth transaction.
    async with async_session_factory() as session:
        yield session
