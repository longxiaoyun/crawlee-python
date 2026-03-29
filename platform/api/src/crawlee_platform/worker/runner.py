"""Execute a single run: prepare workspace, install deps, run user main.py, persist logs."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from crawlee_platform import metrics
from crawlee_platform.config import Settings
from crawlee_platform.models import Run, RunLogLine, TaskVersion


def _pip_module_missing_message() -> str:
    return (
        'This Python has no pip (failed: python -m pip). '
        'Install pip into the API/worker environment, e.g. `cd platform/api && uv sync` '
        '(crawlee-platform lists pip as a dependency), or `uv pip install pip`.'
    )


async def _append_log(session: AsyncSession, run_id: UUID, line_no: int, content: str) -> int:
    session.add(RunLogLine(run_id=run_id, line_no=line_no, content=content))
    await session.commit()
    return line_no + 1


async def execute_run(engine: AsyncEngine, run_id: UUID, settings: Settings) -> None:
    """Load task version, run ``main.py`` in isolated workspace, stream logs to DB."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        run = await session.get(Run, run_id)
        if not run or run.status != 'running':
            return

        version = await session.get(TaskVersion, run.version_id)

        if not version:
            run.status = 'failed'
            run.error_message = 'Task version missing'
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            metrics.runs_failed.labels(kind=run.kind).inc()
            return

        timeout = settings.debug_run_timeout_sec if run.kind == 'debug' else settings.prod_run_timeout_sec
        workspace = Path(tempfile.mkdtemp(prefix='crawl_task_'))
        line_no = 1
        try:
            (workspace / 'main.py').write_text(version.source_code, encoding='utf-8')
            req = version.requirements_txt.strip()
            if req:
                req_lines = [ln for ln in req.splitlines() if ln.strip() and not ln.strip().startswith('#')]
                if run.kind == 'debug' and len(req_lines) > settings.debug_max_pip_packages:
                    msg = 'Too many requirements for debug run'
                    raise ValueError(msg)
                (workspace / 'requirements.txt').write_text(req + '\n', encoding='utf-8')

            line_no = await _append_log(
                session,
                run_id,
                line_no,
                json.dumps(
                    {
                        'severity': 'INFO',
                        'run_id': str(run_id),
                        'task_id': str(run.task_id),
                        'version_id': str(run.version_id),
                        'message': 'Workspace prepared',
                    }
                ),
            )

            deps_dir = workspace / 'deps'
            deps_dir.mkdir(parents=True, exist_ok=True)
            req_path = workspace / 'requirements.txt'
            if req_path.exists():
                if importlib.util.find_spec('pip') is None:
                    raise RuntimeError(_pip_module_missing_message())
                pip_timeout = min(300, timeout)
                proc_pip = await asyncio.create_subprocess_exec(
                    sys.executable,
                    '-m',
                    'pip',
                    'install',
                    '-q',
                    '-r',
                    str(req_path),
                    '--target',
                    str(deps_dir),
                    cwd=str(workspace),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                try:
                    out, _ = await asyncio.wait_for(proc_pip.communicate(), timeout=pip_timeout)
                except TimeoutError:
                    proc_pip.kill()
                    msg = 'pip install timed out'
                    raise TimeoutError(msg) from None
                if proc_pip.returncode != 0:
                    tail = out.decode(errors='replace')[-4000:] if out else ''
                    msg = tail or 'pip install failed'
                    raise RuntimeError(msg)

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONPATH'] = str(deps_dir)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(workspace / 'main.py'),
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

            async def drain_stdout() -> None:
                nonlocal line_no
                assert proc.stdout
                while True:
                    raw = await proc.stdout.readline()
                    if not raw:
                        break
                    line_text = raw.decode(errors='replace').rstrip('\n')
                    line_no = await _append_log(session, run_id, line_no, line_text)

            try:
                await asyncio.wait_for(
                    asyncio.gather(drain_stdout(), proc.wait()),
                    timeout=timeout,
                )
                rc = proc.returncode if proc.returncode is not None else -1
            except TimeoutError:
                proc.kill()
                run.status = 'limit_exceeded'
                run.error_message = 'Wall clock timeout'
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()
                metrics.runs_limit_exceeded.labels(kind=run.kind).inc()
                return

            if rc == 0:
                run.status = 'succeeded'
                metrics.runs_succeeded.labels(kind=run.kind).inc()
            else:
                run.status = 'failed'
                run.error_message = f'Process exited with code {rc}'
                metrics.runs_failed.labels(kind=run.kind).inc()
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:  # noqa: BLE001
            run.status = 'failed'
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            metrics.runs_failed.labels(kind=run.kind).inc()
            line_no = await _append_log(session, run_id, line_no, f'ERROR: {exc!s}')
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


async def claim_next_run(session: AsyncSession) -> Run | None:
    """Mark the oldest queued run as running and return it."""
    run = await session.scalar(
        select(Run).where(Run.status == 'queued').order_by(Run.created_at.asc()).limit(1)
    )
    if run is None:
        return None
    run.status = 'running'
    run.started_at = datetime.now(timezone.utc)
    await session.commit()
    return run
