"""Async database session utilities."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crawlee_platform.config import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_resolved_database_url: str | None = None
_database_backend: str = 'sqlite'


def get_database_backend() -> str:
    """``mysql`` or ``sqlite`` — set after :func:`init_database`."""
    return _database_backend


def reset_database_singleton() -> None:
    """Clear cached engine (tests / reload)."""
    global _engine, _session_factory, _resolved_database_url, _database_backend  # noqa: PLW0603
    if _engine is not None:
        # sync dispose is available; async dispose should be awaited — tests use fresh process often
        _engine = None
    _session_factory = None
    _resolved_database_url = None
    _database_backend = 'sqlite'


def _build_mysql_dsn(settings: Settings) -> str | None:
    if not settings.mysql_host or not settings.mysql_user or not settings.mysql_database:
        return None
    pw = settings.mysql_password if settings.mysql_password is not None else ''
    user = quote_plus(settings.mysql_user)
    password = quote_plus(pw)
    host = settings.mysql_host.strip()
    db = settings.mysql_database.strip()
    port = settings.mysql_port
    return (
        f'mysql+aiomysql://{user}:{password}@{host}:{port}/{db}'
        f'?charset={settings.mysql_charset}'
    )


def _is_mysql_url(url: str) -> bool:
    return url.startswith('mysql') or url.startswith('mariadb')


async def init_database(settings: Settings) -> str:
    """Resolve DB URL: try MySQL when configured; on failure fall back to SQLite.

    Call once from API lifespan and worker startup before :func:`get_engine`.
    """
    global _resolved_database_url, _database_backend  # noqa: PLW0603

    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    if _is_mysql_url(settings.database_url):
        candidates.append(('mysql', settings.database_url))
        seen.add(settings.database_url)

    built = _build_mysql_dsn(settings)
    if built and built not in seen:
        candidates.append(('mysql', built))
        seen.add(built)

    if not candidates:
        _resolved_database_url = settings.database_url
        _database_backend = 'mysql' if _is_mysql_url(settings.database_url) else 'sqlite'
        logger.info('Database: %s', _database_backend)
        return _resolved_database_url

    fallback = settings.sqlite_fallback_url

    for name, url in candidates:
        try:
            eng = create_async_engine(url, echo=False, pool_pre_ping=True)
            async with eng.connect() as conn:
                await conn.execute(text('SELECT 1'))
            await eng.dispose()
            _resolved_database_url = url
            _database_backend = name
            logger.info('Database: %s (connected)', name.upper())
            return url
        except Exception:
            logger.warning('Database: MySQL attempt failed for %s', url[:64])

    _resolved_database_url = fallback
    _database_backend = 'sqlite'
    logger.warning('Database: MySQL unavailable; SQLite fallback (%s)', fallback[:96])
    return fallback


def get_engine(settings: Settings):
    global _engine, _session_factory  # noqa: PLW0603
    url = _resolved_database_url if _resolved_database_url is not None else settings.database_url
    if _engine is None:
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
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
