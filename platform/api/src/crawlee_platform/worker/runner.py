"""Execute a single run: prepare workspace, install deps, run user main.py, persist logs."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from crawlee_platform import metrics
from crawlee_platform.config import Settings
from crawlee_platform.models import Run, RunDatasetItem, RunLogLine, TaskVersion
from crawlee_platform.worker.patch_crawlee_playwright_goto import patch_playwright_goto_duplicate_timeout
from crawlee_platform.worker.patch_crawlee_types import patch_crawlee_types_default_desired
from crawlee_platform.worker.source_normalize import normalization_diagnostics

logger = logging.getLogger(__name__)


def _requirement_line_installs_crawlee_package(line: str) -> bool:
    """Return whether a pip requirements line installs the ``crawlee`` distribution (not ``crawlee-*``)."""
    main = line.split('#', 1)[0].strip()
    if not main:
        return False
    main = main.split(';', 1)[0].strip()
    token = main.split()[0]
    token = token.split('[', 1)[0]
    token = token.split('@', 1)[0].strip()
    for sep in ('==', '>=', '<=', '~=', '!=', '>', '<'):
        if sep in token:
            token = token.split(sep, 1)[0]
            break
    return token == 'crawlee'


def _requirements_without_crawlee(requirements_txt: str) -> str:
    lines = [ln for ln in requirements_txt.splitlines() if not _requirement_line_installs_crawlee_package(ln)]
    return '\n'.join(lines)


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


async def _persist_crawlee_default_dataset(session: AsyncSession, run_id: UUID, workspace: Path) -> None:
    """Import ``storage/datasets/default/*.json`` (Crawlee filesystem layout) into run_dataset_items."""
    await session.execute(delete(RunDatasetItem).where(RunDatasetItem.run_id == run_id))
    dataset_dir = workspace / 'storage' / 'datasets' / 'default'
    if not dataset_dir.is_dir():
        await session.commit()
        return
    files = sorted(
        (p for p in dataset_dir.glob('*.json') if p.name != '__metadata__.json' and p.stem.isdigit()),
        key=lambda p: int(p.stem),
    )
    for seq, path in enumerate(files, start=1):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            session.add(RunDatasetItem(run_id=run_id, seq=seq, payload=data))
    await session.commit()


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
        dataset_imported = False
        try:
            normalized_source = settings.task_source_for_run_and_storage(version.source_code)
            (workspace / 'main.py').write_text(normalized_source, encoding='utf-8')
            diag = normalization_diagnostics(version.source_code, normalized_source)
            logger.info(
                'run %s task_source_normalize: changed=%s len %s->%s still_suspect=%s',
                run_id,
                diag['source_changed'],
                diag['len_before'],
                diag['len_after'],
                diag['still_suspect'],
            )
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
                        'message': 'task_source_normalize',
                        'source_changed': diag['source_changed'],
                        'len_before': diag['len_before'],
                        'len_after': diag['len_after'],
                        'still_suspect_missing_desired': diag['still_suspect'],
                    }
                ),
            )
            req = version.requirements_txt.strip()
            if settings.crawlee_source_path is not None and settings.effective_crawlee_source_path is None:
                logger.warning(
                    'PLATFORM_CRAWLEE_SOURCE_PATH does not point to a directory containing crawlee/: %s',
                    settings.crawlee_source_path,
                )
            local_crawlee = settings.effective_crawlee_source_path
            req_for_pip = _requirements_without_crawlee(req) if local_crawlee is not None else req
            if req_for_pip.strip():
                req_lines = [ln for ln in req_for_pip.splitlines() if ln.strip() and not ln.strip().startswith('#')]
                if run.kind == 'debug' and len(req_lines) > settings.debug_max_pip_packages:
                    msg = 'Too many requirements for debug run'
                    raise ValueError(msg)
                (workspace / 'requirements.txt').write_text(req_for_pip.strip() + '\n', encoding='utf-8')

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

                crawlee_src_for_prune = settings.effective_crawlee_source_path
                if crawlee_src_for_prune is not None:
                    pruned = deps_dir / 'crawlee'
                    if pruned.exists():
                        shutil.rmtree(pruned, ignore_errors=True)
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
                                    'message': 'removed_deps_crawlee_shadow',
                                    'reason': 'local_crawlee_src_configured',
                                }
                            ),
                        )

                # Patch PyPI wheel files under ``deps`` when present (local ``src`` should win on
                # PYTHONPATH; see also ``removed_deps_crawlee_shadow``).
                types_patched = patch_crawlee_types_default_desired(deps_dir)
                playwright_goto_patched = patch_playwright_goto_duplicate_timeout(deps_dir)
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
                            'message': 'crawlee_deps_patches',
                            'types_patched': types_patched,
                            'playwright_goto_patched': playwright_goto_patched,
                        }
                    ),
                )

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            crawlee_src = settings.effective_crawlee_source_path
            path_parts: list[str] = []
            if crawlee_src is not None:
                path_parts.append(str(crawlee_src))
            path_parts.append(str(deps_dir))
            env['PYTHONPATH'] = os.pathsep.join(path_parts)
            if crawlee_src is not None:
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
                            'message': 'worker_pythonpath',
                            'crawlee_source': str(crawlee_src),
                            'deps_target': str(deps_dir),
                        }
                    ),
                )

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

            # Import default dataset before committing terminal status so clients never see
            # ``succeeded`` with an empty ``run_dataset_items`` row set (race with UI polling).
            await _persist_crawlee_default_dataset(session, run_id, workspace)
            dataset_imported = True

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
            if not dataset_imported:
                try:
                    await _persist_crawlee_default_dataset(session, run_id, workspace)
                except Exception:
                    logger.exception('Failed to persist Crawlee default dataset for run %s', run_id)
            shutil.rmtree(workspace, ignore_errors=True)


async def claim_next_run(session: AsyncSession) -> Run | None:
    """Mark the oldest queued run as running and return it."""
    run = await session.scalar(select(Run).where(Run.status == 'queued').order_by(Run.created_at.asc()).limit(1))
    if run is None:
        return None
    run.status = 'running'
    run.started_at = datetime.now(timezone.utc)
    await session.commit()
    return run
