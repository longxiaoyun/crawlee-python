"""Poll queued runs and execute them."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from crawlee_platform import metrics
from crawlee_platform.config import Settings
from crawlee_platform.models import Base, WorkerHeartbeat
from crawlee_platform.worker.runner import claim_next_run, execute_run


async def _heartbeat(
    factory: async_sessionmaker,
) -> None:
    async with factory() as session:
        row = await session.get(WorkerHeartbeat, 1)
        if row is None:
            session.add(
                WorkerHeartbeat(id=1, worker_id=os.environ.get('PLATFORM_WORKER_ID', 'default'))
            )
        else:
            row.updated_at = datetime.now(timezone.utc)
        await session.commit()
    metrics.worker_last_heartbeat_unix.set(time.time())


async def _async_main() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    while True:
        async with factory() as session:
            run = await claim_next_run(session)
            run_id = run.id if run else None

        if run_id is not None:
            await execute_run(engine, run_id, settings)

        await _heartbeat(factory)
        await asyncio.sleep(0.5)


def run() -> None:
    """Entrypoint for ``python -m crawlee_platform.worker.main``."""
    asyncio.run(_async_main())


if __name__ == '__main__':
    run()
