"""Pytest fixtures for platform API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from crawlee_platform import db as db_module
from crawlee_platform.api_app import app
from crawlee_platform.config import Settings
from crawlee_platform.db import get_engine
from crawlee_platform.deps import get_settings_cached
from crawlee_platform.models import Base


@pytest.fixture
async def platform_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    db_path = tmp_path / 'platform-test.db'
    monkeypatch.setenv('PLATFORM_DATABASE_URL', f'sqlite+aiosqlite:///{db_path}')
    monkeypatch.setenv('PLATFORM_API_KEY', 'test-key')
    monkeypatch.setenv('PLATFORM_DEBUG_RUN_TIMEOUT_SEC', '60')
    get_settings_cached.cache_clear()
    db_module._engine = None  # noqa: SLF001
    db_module._session_factory = None  # noqa: SLF001
    settings = Settings()
    engine = get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test', timeout=30) as client:
        yield client


def headers() -> dict[str, str]:
    return {'X-API-Key': 'test-key'}
