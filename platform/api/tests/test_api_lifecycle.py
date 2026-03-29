"""Integration-style tests for task and run lifecycle."""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from crawlee_platform.config import Settings
from crawlee_platform.models import Base
from crawlee_platform.worker.runner import claim_next_run, execute_run


def _headers() -> dict[str, str]:
    return {'X-API-Key': 'test-key'}


@pytest.mark.asyncio
async def test_new_task_has_initial_build_0_0_1(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'seeded', 'description': ''}, headers=_headers())
    r.raise_for_status()
    body = r.json()
    task_id = body['id']
    assert body.get('production_version_id') is not None

    r = await platform_client.get(f'/api/tasks/{task_id}/versions', headers=_headers())
    r.raise_for_status()
    versions = r.json()
    assert len(versions) == 1
    assert versions[0]['version_number'] == 1
    assert versions[0]['id'] == body['production_version_id']
    assert 'async def main' in versions[0]['source_code']
    assert 'crawlee' in versions[0]['source_code']
    assert 'beautifulsoup' in versions[0]['requirements_txt'].lower()


@pytest.mark.asyncio
async def test_task_crud_and_debug_run(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'demo', 'description': ''}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']

    code = 'print("hello from task")' + '\n'
    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': code, 'requirements_txt': '', 'meta': {}, 'created_by': 'tester'},
        headers=_headers(),
    )
    r.raise_for_status()
    version_id = r.json()['id']

    r = await platform_client.post(
        f'/api/tasks/{task_id}/runs',
        json={'version_id': version_id, 'kind': 'debug'},
        headers=_headers(),
    )
    r.raise_for_status()
    run_id = r.json()['id']

    settings = Settings()
    assert settings.database_url == os.environ['PLATFORM_DATABASE_URL']
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        run = await claim_next_run(session)
        assert run is not None
        claimed_id = run.id

    assert str(claimed_id) == run_id
    await execute_run(engine, UUID(run_id), settings)
    await engine.dispose()

    r = await platform_client.get(f'/api/runs/{run_id}', headers=_headers())
    r.raise_for_status()
    body = r.json()
    assert body['status'] == 'succeeded'

    logs = await platform_client.get(f'/api/runs/{run_id}/logs', headers=_headers())
    logs.raise_for_status()
    text = '\n'.join(line['content'] for line in logs.json())
    assert 'hello from task' in text


@pytest.mark.asyncio
async def test_production_run_requires_promote(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'p', 'description': ''}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']

    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': 'print(1)\n', 'requirements_txt': ''},
        headers=_headers(),
    )
    r.raise_for_status()
    version_id = r.json()['id']

    r = await platform_client.post(
        f'/api/tasks/{task_id}/runs',
        json={'version_id': version_id, 'kind': 'production'},
        headers=_headers(),
    )
    assert r.status_code == 400

    r = await platform_client.post(
        f'/api/tasks/{task_id}/promote',
        json={'version_id': version_id},
        headers=_headers(),
    )
    r.raise_for_status()

    r = await platform_client.post(
        f'/api/tasks/{task_id}/runs',
        json={'version_id': version_id, 'kind': 'production'},
        headers=_headers(),
    )
    r.raise_for_status()
    assert r.json()['kind'] == 'production'


@pytest.mark.asyncio
async def test_create_version_rejects_javascript_template_literals(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'js-bad', 'description': ''}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']

    bad = (
        'async def main():\n'
        '    links = []\n'
        '    log.info(`采集到约 ${links.length} 条链接（示例）`)\n'
    )
    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': bad, 'requirements_txt': '', 'meta': {}, 'created_by': 'tester'},
        headers=_headers(),
    )
    assert r.status_code == 400
    assert 'JavaScript' in r.json()['detail'] or 'f-strings' in r.json()['detail']


@pytest.mark.asyncio
async def test_create_version_rejects_python_syntax_error(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'syntax-bad', 'description': ''}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']

    bad = 'async def main():\n    x = (\n'
    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': bad, 'requirements_txt': '', 'meta': {}, 'created_by': 'tester'},
        headers=_headers(),
    )
    assert r.status_code == 400
    assert 'syntax error' in r.json()['detail'].lower()


@pytest.mark.asyncio
async def test_overview_requires_auth(platform_client: AsyncClient) -> None:
    r = await platform_client.get('/api/overview')
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_task_settings_merge(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 's', 'description': 'd0'}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']
    assert r.json().get('settings') == {}

    r = await platform_client.patch(
        f'/api/tasks/{task_id}',
        json={'settings': {'webhook_url': 'https://example.com/hook'}},
        headers=_headers(),
    )
    r.raise_for_status()
    assert r.json()['settings']['webhook_url'] == 'https://example.com/hook'

    r = await platform_client.patch(
        f'/api/tasks/{task_id}',
        json={'settings': {'visibility': 'private'}},
        headers=_headers(),
    )
    r.raise_for_status()
    s = r.json()['settings']
    assert s['webhook_url'] == 'https://example.com/hook'
    assert s['visibility'] == 'private'


@pytest.mark.asyncio
async def test_deploy_requires_crawlee_contract(platform_client: AsyncClient) -> None:
    r = await platform_client.post('/api/tasks', json={'name': 'deployable', 'description': ''}, headers=_headers())
    r.raise_for_status()
    task_id = r.json()['id']

    bad_code = 'def main():\n    print("not async")\n'
    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': bad_code, 'requirements_txt': ''},
        headers=_headers(),
    )
    r.raise_for_status()
    bad_version = r.json()['id']

    r = await platform_client.post(
        f'/api/tasks/{task_id}/promote',
        json={'version_id': bad_version},
        headers=_headers(),
    )
    r.raise_for_status()

    r = await platform_client.post(
        f'/api/tasks/{task_id}/deploy',
        json={},
        headers=_headers(),
    )
    assert r.status_code == 400

    good_code = (
        'from crawlee import HttpCrawler\n\n'
        'async def main() -> None:\n'
        '    crawler = HttpCrawler()\n'
        '    await crawler.run([])\n'
    )
    r = await platform_client.post(
        f'/api/tasks/{task_id}/versions',
        json={'source_code': good_code, 'requirements_txt': 'crawlee>=0.1\n'},
        headers=_headers(),
    )
    r.raise_for_status()
    good_version = r.json()['id']

    r = await platform_client.post(
        f'/api/tasks/{task_id}/promote',
        json={'version_id': good_version},
        headers=_headers(),
    )
    r.raise_for_status()

    r = await platform_client.post(
        f'/api/tasks/{task_id}/deploy',
        json={},
        headers=_headers(),
    )
    r.raise_for_status()
    deployed = r.json()
    assert deployed['status'] == 'deployed'
    assert deployed['runtime'] == 'crawlee'
