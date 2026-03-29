"""Async database session utilities."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crawlee_platform.config import Settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings):
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        msg = 'Database not initialized; call get_engine first'
        raise RuntimeError(msg)
    return _session_factory


async def get_session(settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    get_engine(settings)
    factory = session_factory()
    async with factory() as session:
        yield session
