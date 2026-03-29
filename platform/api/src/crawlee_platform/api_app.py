"""FastAPI application: control plane API."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from crawlee_platform.ai_service import complete_chat
from crawlee_platform.auth import _api_key_header, require_api_key
from crawlee_platform.config import Settings
from crawlee_platform.db import get_engine
from crawlee_platform.deps import get_settings
from crawlee_platform import metrics as platform_metrics
from crawlee_platform.models import Base, ChatMessage, Run, RunLogLine, Task, TaskVersion, WorkerHeartbeat
from crawlee_platform.schemas import (
    ChatRequest,
    ChatResponse,
    DeployOut,
    DeployRequest,
    OverviewOut,
    PromoteBody,
    RunCreate,
    RunOut,
    TaskCreate,
    TaskListRowOut,
    TaskOut,
    TaskUpdate,
    TaskVersionCreate,
    TaskVersionOut,
)


async def _ensure_sqlite_task_settings_column(engine) -> None:
    """Add tasks.settings for existing SQLite files (create_all does not ALTER)."""
    if engine.dialect.name != 'sqlite':
        return
    async with engine.begin() as conn:
        result = await conn.execute(text('PRAGMA table_info(tasks)'))
        col_names = {row[1] for row in result.fetchall()}
        if 'settings' not in col_names:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN settings TEXT DEFAULT '{}'"))


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    settings = get_settings()
    engine = get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_sqlite_task_settings_column(engine)
    await _ensure_tasks_have_initial_version(engine)
    yield


app = FastAPI(title='Crawlee Platform API', lifespan=_lifespan)


def _configure_cors(application: FastAPI, settings: Settings) -> None:
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )


_configure_cors(app, get_settings())


def _as_utc(dt: datetime) -> datetime:
    """Normalize to UTC for arithmetic/serialization (SQLite may return naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_crawlee_source(source_code: str) -> None:
    """Basic guardrails so published code matches Crawlee runtime contract."""
    checks = {
        'async_main': 'async def main' in source_code,
        'crawlee_import': ('from crawlee' in source_code) or ('import crawlee' in source_code),
    }
    if all(checks.values()):
        return
    missing = []
    if not checks['async_main']:
        missing.append('`async def main(...)` entry function')
    if not checks['crawlee_import']:
        missing.append('a Crawlee import (`from crawlee ...` or `import crawlee`)')
    detail = 'Deployment blocked: source is not Crawlee-compatible, missing ' + ', '.join(missing)
    raise HTTPException(status_code=400, detail=detail)


_JS_TEMPLATE_LITERAL_RE = re.compile(r'`[^`\n]*\$\{')


def _validate_saved_main_py(source_code: str) -> None:
    """Reject obvious non-Python (e.g. JS template strings) and invalid Python before persisting a version."""
    if _JS_TEMPLATE_LITERAL_RE.search(source_code):
        raise HTTPException(
            status_code=400,
            detail=(
                'main.py contains JavaScript-style template literals (backticks with ${...}). '
                'In Python use f-strings, e.g. context.log.info(f"count {len(links)}") instead of '
                '`...${links.length}...`, and use len(links) instead of links.length.'
            ),
        )
    try:
        compile(source_code, 'main.py', 'exec')
    except SyntaxError as e:
        lineno = e.lineno or 0
        off = (e.offset or 1) - 1
        line_snip = (e.text or '').strip()
        pointer = (' ' * max(0, off) + '^') if e.text and off >= 0 else ''
        tail = '\n'.join(x for x in (line_snip, pointer) if x)[:200]
        raise HTTPException(
            status_code=400,
            detail=(
                f'Python syntax error in main.py (line {lineno}): {e.msg}. '
                'If you pasted JavaScript, use Python syntax (f-strings, len(x) not x.length). '
                + (f'Context:\n{tail}' if tail else '')
            ),
        ) from None


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    engine = get_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


AsyncSessionDep = Annotated[AsyncSession, Depends(get_db_session)]

# First build is 0.0.1 (patch = version_number 1); each new version increments patch.
# Runnable Crawlee template (worker runs `python main.py` with same interpreter; deps from requirements.txt).
DEFAULT_TASK_SOURCE = '''import asyncio

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext


async def main() -> None:
    """Minimal Crawlee crawler — edit URLs and handler as needed."""
    crawler = BeautifulSoupCrawler(max_requests_per_crawl=5)

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        context.log.info(f"Processing {context.request.url} ...")
        title_el = context.soup.title
        title = title_el.get_text(strip=True) if title_el else None
        await context.push_data({"url": context.request.url, "title": title})

    await crawler.run(["https://crawlee.dev"])


if __name__ == "__main__":
    asyncio.run(main())
'''

# Explicit beautifulsoup4: `pip install --target deps` + PYTHONPATH=deps must contain bs4;
# otherwise import falls back to a global editable crawlee without the optional extra.
DEFAULT_TASK_REQUIREMENTS = (
    'crawlee[beautifulsoup]\n'
    'beautifulsoup4>=4.12.0\n'
    'html5lib>=1.0\n'
)


async def _ensure_tasks_have_initial_version(engine) -> None:
    """Backfill: every task has at least build 0.0.1 so the console can always run/debug."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        tasks = (await session.scalars(select(Task))).all()
        dirty = False
        for task in tasks:
            cnt = await session.scalar(select(func.count()).where(TaskVersion.task_id == task.id))
            if cnt and cnt > 0:
                continue
            ver = TaskVersion(
                task_id=task.id,
                version_number=1,
                source_code=DEFAULT_TASK_SOURCE,
                requirements_txt=DEFAULT_TASK_REQUIREMENTS,
                meta={},
                created_by='system',
            )
            session.add(ver)
            await session.flush()
            if task.production_version_id is None:
                task.production_version_id = ver.id
            dirty = True
        if dirty:
            await session.commit()


async def require_key(_: Annotated[None, Depends(require_api_key)]) -> None:
    """Marker dependency for protected routes."""


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/metrics')
async def prometheus_metrics(
    settings: Annotated[Settings, Depends(get_settings)],
    session: AsyncSessionDep,
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> Response:
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail='Invalid or missing API key')

    queued = await session.scalar(select(func.count()).select_from(Run).where(Run.status == 'queued')) or 0
    running = await session.scalar(select(func.count()).select_from(Run).where(Run.status == 'running')) or 0
    platform_metrics.runs_queued.set(queued)
    platform_metrics.runs_running.set(running)

    hb = await session.get(WorkerHeartbeat, 1)
    if hb and hb.updated_at:
        platform_metrics.worker_last_heartbeat_unix.set(_as_utc(hb.updated_at).timestamp())
    else:
        platform_metrics.worker_last_heartbeat_unix.set(0)

    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.get('/api/overview', dependencies=[Depends(require_key)])
async def overview(
    settings: Annotated[Settings, Depends(get_settings)],
    session: AsyncSessionDep,
) -> OverviewOut:
    hb = await session.get(WorkerHeartbeat, 1)
    hb_time = hb.updated_at if hb else None
    stale = True
    if hb_time is not None:
        age = datetime.now(timezone.utc) - _as_utc(hb_time)
        stale = age.total_seconds() > settings.worker_heartbeat_stale_sec

    recent = (
        await session.scalars(select(Run).order_by(Run.created_at.desc()).limit(100))
    ).all()
    finished = [r for r in recent if r.status in {'succeeded', 'failed', 'limit_exceeded'}]
    ok = sum(1 for r in finished if r.status == 'succeeded')
    ratio = (ok / len(finished)) if finished else 0.0

    queued = await session.scalar(select(func.count()).select_from(Run).where(Run.status == 'queued')) or 0
    running = await session.scalar(select(func.count()).select_from(Run).where(Run.status == 'running')) or 0

    return OverviewOut(
        worker_heartbeat_at=_as_utc(hb_time) if hb_time is not None else None,
        worker_stale=stale,
        recent_success_ratio=ratio,
        queued_runs=queued,
        running_runs=running,
    )


def _run_last_activity_at(r: Run) -> datetime:
    if r.finished_at is not None:
        return _as_utc(r.finished_at)
    if r.started_at is not None:
        return _as_utc(r.started_at)
    return _as_utc(r.created_at)


def _run_duration_seconds(r: Run) -> float | None:
    if r.started_at is None or r.finished_at is None:
        return None
    return (_as_utc(r.finished_at) - _as_utc(r.started_at)).total_seconds()


@app.get('/api/tasks', dependencies=[Depends(require_key)])
async def list_tasks(session: AsyncSessionDep) -> list[TaskListRowOut]:
    tasks = (await session.scalars(select(Task).order_by(Task.updated_at.desc()))).all()
    if not tasks:
        return []
    task_ids = [t.id for t in tasks]

    v_count_rows = (
        await session.execute(
            select(TaskVersion.task_id, func.count(TaskVersion.id))
            .where(TaskVersion.task_id.in_(task_ids))
            .group_by(TaskVersion.task_id)
        )
    ).all()
    vc_map = {row[0]: int(row[1]) for row in v_count_rows}

    latest_sub = (
        select(TaskVersion.task_id, func.max(TaskVersion.version_number).label('mx'))
        .where(TaskVersion.task_id.in_(task_ids))
        .group_by(TaskVersion.task_id)
        .subquery()
    )
    latest_rows = (
        await session.execute(
            select(TaskVersion.task_id, TaskVersion.id, TaskVersion.version_number).join(
                latest_sub,
                (TaskVersion.task_id == latest_sub.c.task_id) & (TaskVersion.version_number == latest_sub.c.mx),
            )
        )
    ).all()
    latest_map: dict[UUID, tuple[UUID, int]] = {}
    for tid, vid, vn in latest_rows:
        latest_map[tid] = (vid, int(vn))

    prod_ids = [t.production_version_id for t in tasks if t.production_version_id]
    prod_vn_by_version_id: dict[UUID, int] = {}
    if prod_ids:
        pv_rows = (
            await session.execute(select(TaskVersion.id, TaskVersion.version_number).where(TaskVersion.id.in_(prod_ids)))
        ).all()
        prod_vn_by_version_id = {row[0]: int(row[1]) for row in pv_rows}

    r_count_rows = (
        await session.execute(
            select(Run.task_id, func.count(Run.id)).where(Run.task_id.in_(task_ids)).group_by(Run.task_id)
        )
    ).all()
    rc_map = {row[0]: int(row[1]) for row in r_count_rows}

    sub_mx = (
        select(Run.task_id, func.max(Run.created_at).label('mx'))
        .where(Run.task_id.in_(task_ids))
        .group_by(Run.task_id)
        .subquery()
    )
    last_run_candidates = (
        await session.scalars(
            select(Run).join(
                sub_mx,
                (Run.task_id == sub_mx.c.task_id) & (Run.created_at == sub_mx.c.mx),
            )
        )
    ).all()
    last_by_task: dict[UUID, Run] = {}
    for r in last_run_candidates:
        prev = last_by_task.get(r.task_id)
        if prev is None or str(r.id) > str(prev.id):
            last_by_task[r.task_id] = r

    out: list[TaskListRowOut] = []
    for t in tasks:
        tb = vc_map.get(t.id, 0)
        tr = rc_map.get(t.id, 0)
        latest_pair = latest_map.get(t.id)
        latest_id, latest_vn = (latest_pair[0], latest_pair[1]) if latest_pair else (None, 0)
        prod_id = t.production_version_id
        if latest_vn == 0:
            dbd = '—'
        elif prod_id is None or prod_id == latest_id:
            dbd = f'latest / 0.0.{latest_vn}'
        else:
            pvn = prod_vn_by_version_id.get(prod_id, latest_vn)
            dbd = f'0.0.{pvn}'

        lr = last_by_task.get(t.id)
        last_at = _run_last_activity_at(lr) if lr else None
        last_st = lr.status if lr else None
        last_dur = _run_duration_seconds(lr) if lr else None

        base = TaskOut.model_validate(t).model_dump()
        out.append(
            TaskListRowOut.model_validate(
                {
                    **base,
                    'total_builds': tb,
                    'total_runs': tr,
                    'default_build_display': dbd,
                    'last_run_at': last_at,
                    'last_run_status': last_st,
                    'last_run_duration_sec': last_dur,
                }
            )
        )
    return out


@app.post('/api/tasks', dependencies=[Depends(require_key)])
async def create_task(session: AsyncSessionDep, body: TaskCreate) -> TaskOut:
    task = Task(name=body.name, description=body.description)
    session.add(task)
    await session.flush()
    ver = TaskVersion(
        task_id=task.id,
        version_number=1,
        source_code=DEFAULT_TASK_SOURCE,
        requirements_txt=DEFAULT_TASK_REQUIREMENTS,
        meta={},
        created_by='system',
    )
    session.add(ver)
    await session.flush()
    task.production_version_id = ver.id
    await session.commit()
    await session.refresh(task)
    return TaskOut.model_validate(task)


@app.get('/api/tasks/{task_id}', dependencies=[Depends(require_key)])
async def get_task(task_id: UUID, session: AsyncSessionDep) -> TaskOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return TaskOut.model_validate(task)


@app.patch('/api/tasks/{task_id}', dependencies=[Depends(require_key)])
async def update_task(task_id: UUID, session: AsyncSessionDep, body: TaskUpdate) -> TaskOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    if body.name is not None:
        task.name = body.name
    if body.description is not None:
        task.description = body.description
    if body.settings is not None:
        merged = dict(task.settings or {})
        merged.update(body.settings)
        task.settings = merged
    await session.commit()
    await session.refresh(task)
    return TaskOut.model_validate(task)


@app.delete('/api/tasks/{task_id}', dependencies=[Depends(require_key)])
async def delete_task(task_id: UUID, session: AsyncSessionDep) -> Response:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    await session.execute(
        delete(RunLogLine).where(RunLogLine.run_id.in_(select(Run.id).where(Run.task_id == task_id)))
    )
    await session.execute(delete(Run).where(Run.task_id == task_id))
    await session.execute(delete(TaskVersion).where(TaskVersion.task_id == task_id))
    await session.execute(delete(ChatMessage).where(ChatMessage.task_id == task_id))
    await session.delete(task)
    await session.commit()
    return Response(status_code=204)


@app.get('/api/tasks/{task_id}/versions', dependencies=[Depends(require_key)])
async def list_versions(task_id: UUID, session: AsyncSessionDep) -> list[TaskVersionOut]:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    rows = (
        await session.scalars(
            select(TaskVersion).where(TaskVersion.task_id == task_id).order_by(TaskVersion.version_number.desc())
        )
    ).all()
    return [TaskVersionOut.model_validate(r) for r in rows]


@app.post('/api/tasks/{task_id}/versions', dependencies=[Depends(require_key)])
async def create_version(
    task_id: UUID,
    session: AsyncSessionDep,
    body: TaskVersionCreate,
) -> TaskVersionOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    _validate_saved_main_py(body.source_code)
    last_num = await session.scalar(
        select(func.max(TaskVersion.version_number)).where(TaskVersion.task_id == task_id)
    )
    next_num = (last_num or 0) + 1
    ver = TaskVersion(
        task_id=task_id,
        version_number=next_num,
        source_code=body.source_code,
        requirements_txt=body.requirements_txt,
        meta=body.meta,
        created_by=body.created_by,
    )
    session.add(ver)
    await session.commit()
    await session.refresh(ver)
    return TaskVersionOut.model_validate(ver)


@app.post('/api/tasks/{task_id}/promote', dependencies=[Depends(require_key)])
async def promote_version(task_id: UUID, session: AsyncSessionDep, body: PromoteBody) -> TaskOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    ver = await session.get(TaskVersion, body.version_id)
    if not ver or ver.task_id != task_id:
        raise HTTPException(status_code=400, detail='Version does not belong to task')
    task.production_version_id = ver.id
    await session.commit()
    await session.refresh(task)
    return TaskOut.model_validate(task)


@app.post('/api/tasks/{task_id}/deploy', dependencies=[Depends(require_key)])
async def deploy_task(task_id: UUID, session: AsyncSessionDep, body: DeployRequest) -> DeployOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    target_version_id = body.version_id or task.production_version_id
    if target_version_id is None:
        raise HTTPException(status_code=400, detail='Set a default version before deployment')

    ver = await session.get(TaskVersion, target_version_id)
    if not ver or ver.task_id != task_id:
        raise HTTPException(status_code=400, detail='Version does not belong to task')

    _validate_crawlee_source(ver.source_code)

    deployed_at = datetime.now(timezone.utc)
    current_settings = dict(task.settings or {})
    current_settings['deployment'] = {
        'status': 'deployed',
        'environment': body.environment,
        'runtime': 'crawlee',
        'entrypoint': 'main.py',
        'version_id': str(ver.id),
        'deployed_at': deployed_at.isoformat(),
    }
    task.settings = current_settings
    await session.commit()

    return DeployOut(
        task_id=task_id,
        version_id=ver.id,
        environment=body.environment,
        runtime='crawlee',
        entrypoint='main.py',
        deployed_at=deployed_at,
        status='deployed',
    )


@app.post('/api/tasks/{task_id}/runs', dependencies=[Depends(require_key)])
async def enqueue_run(
    task_id: UUID,
    session: AsyncSessionDep,
    body: RunCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RunOut:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    ver = await session.get(TaskVersion, body.version_id)
    if not ver or ver.task_id != task_id:
        raise HTTPException(status_code=400, detail='Version does not belong to task')

    if body.kind == 'production':
        if task.production_version_id is None:
            raise HTTPException(status_code=400, detail='Promote a version before production runs')
        if task.production_version_id != body.version_id:
            raise HTTPException(
                status_code=400,
                detail='Production runs MUST target the promoted production version',
            )

    run = Run(task_id=task_id, version_id=body.version_id, kind=body.kind, status='queued')
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return RunOut.model_validate(run)


@app.get('/api/runs/{run_id}', dependencies=[Depends(require_key)])
async def get_run(run_id: UUID, session: AsyncSessionDep) -> RunOut:
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return RunOut.model_validate(run)


@app.get('/api/tasks/{task_id}/runs', dependencies=[Depends(require_key)])
async def list_runs(task_id: UUID, session: AsyncSessionDep) -> list[RunOut]:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    rows = (await session.scalars(select(Run).where(Run.task_id == task_id).order_by(Run.created_at.desc()))).all()
    return [RunOut.model_validate(r) for r in rows]


@app.get('/api/runs/{run_id}/logs', dependencies=[Depends(require_key)])
async def get_logs(run_id: UUID, session: AsyncSessionDep) -> list[dict[str, int | str]]:
    rows = (
        await session.scalars(
            select(RunLogLine).where(RunLogLine.run_id == run_id).order_by(RunLogLine.line_no.asc())
        )
    ).all()
    return [{'line_no': r.line_no, 'content': r.content} for r in rows]


@app.get('/api/runs/{run_id}/logs/stream', dependencies=[Depends(require_key)])
async def stream_logs(
    run_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    async def gen() -> AsyncGenerator[str, None]:
        engine = get_engine(settings)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        last_line = 0
        terminal = {'succeeded', 'failed', 'cancelled', 'limit_exceeded'}
        while True:
            async with factory() as session:
                run = await session.get(Run, run_id)
                if not run:
                    yield f'data: {json.dumps({"error": "not found"})}\n\n'
                    break
                lines = (
                    (
                        await session.scalars(
                            select(RunLogLine)
                            .where(RunLogLine.run_id == run_id, RunLogLine.line_no > last_line)
                            .order_by(RunLogLine.line_no.asc())
                        )
                    )
                    .all()
                )
                for line in lines:
                    last_line = line.line_no
                    yield f'data: {json.dumps({"content": line.content})}\n\n'
                await session.refresh(run)
                if run.status in terminal:
                    yield f'data: {json.dumps({"done": True, "status": run.status})}\n\n'
                    break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type='text/event-stream')


@app.post('/api/tasks/{task_id}/chat', dependencies=[Depends(require_key)])
async def chat(
    task_id: UUID,
    session: AsyncSessionDep,
    body: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    session.add(ChatMessage(task_id=task_id, role='user', content=body.message))
    await session.commit()

    reply, correlation_id, model_id = await complete_chat(settings=settings, user_message=body.message)

    session.add(
        ChatMessage(
            task_id=task_id,
            role='assistant',
            content=reply,
            model_id=model_id,
            correlation_id=correlation_id,
        )
    )
    await session.commit()
    return ChatResponse(reply=reply, correlation_id=correlation_id, model_id=model_id)


@app.get('/api/tasks/{task_id}/chat', dependencies=[Depends(require_key)])
async def list_chat(task_id: UUID, session: AsyncSessionDep) -> list[dict[str, str | None]]:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    rows = (
        await session.scalars(
            select(ChatMessage).where(ChatMessage.task_id == task_id).order_by(ChatMessage.created_at.asc())
        )
    ).all()
    return [
        {
            'role': r.role,
            'content': r.content,
            'correlation_id': r.correlation_id,
            'model_id': r.model_id,
        }
        for r in rows
    ]


def run() -> None:
    """CLI entry for uvicorn."""
    import uvicorn

    uvicorn.run('crawlee_platform.api_app:app', host='0.0.0.0', port=8000, reload=False)
