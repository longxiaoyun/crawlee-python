"""Opt-in live crawl of juejin.cn (Playwright).

Output of the sample script:

- **Dataset**: ``(await crawler.get_data()).items`` — one dict per article **detail** page
  (URL contains ``/post/``), with keys ``url``, ``title``, ``content`` (first 500 chars),
  ``crawled_at`` (UTC ISO string). The home page does not call ``push_data``.

- **On disk** (with ``Configuration(storage_dir=...)`` and ``FileSystemStorageClient``):
  Crawlee storage layout under that directory, including dataset JSON files.

Run (needs network + Playwright browsers)::

    CRAWLEE_TEST_JUEJIN=1 uv run pytest tests/integration/test_juejin_playwright_sample.py -v --no-cov

Skipped by default (no env / CI).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.network_live
@pytest.mark.skipif(
    os.environ.get('CRAWLEE_TEST_JUEJIN') != '1',
    reason='Set CRAWLEE_TEST_JUEJIN=1 to run live Juejin crawl (external network).',
)
async def test_juejin_sample_produces_post_dataset_items(tmp_path: Path) -> None:
    """End-to-end: home -> article links -> detail pages -> dataset rows."""
    pytest.importorskip('playwright')

    from crawlee import ConcurrencySettings  # noqa: PLC0415
    from crawlee.configuration import Configuration  # noqa: PLC0415
    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext  # noqa: PLC0415
    from crawlee.storage_clients import FileSystemStorageClient  # noqa: PLC0415

    configuration = Configuration(storage_dir=str(tmp_path))
    storage_client = FileSystemStorageClient()

    crawler = PlaywrightCrawler(
        configuration=configuration,
        storage_client=storage_client,
        headless=True,
        max_requests_per_crawl=25,
        concurrency_settings=ConcurrencySettings(
            min_concurrency=1,
            max_concurrency=2,
            desired_concurrency=2,
        ),
        request_handler_timeout=timedelta(seconds=90),
        goto_options={'wait_until': 'networkidle', 'timeout': 45_000},
    )

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        page = context.page
        url = context.request.url

        if '/post/' in url:
            await page.wait_for_timeout(1500)
            await page.wait_for_selector('h1.article-title', timeout=15_000)
            data = await page.evaluate(
                """() => {
                const title = document.querySelector('h1.article-title')?.innerText || '无标题';
                const content = document.querySelector('.article-content')?.innerText || '无内容';
                return { title, content };
            }"""
            )
            await context.push_data(
                {
                    'url': url,
                    'title': data['title'],
                    'content': (data['content'] or '').strip()[:500],
                    'crawled_at': datetime.now(timezone.utc).isoformat(),
                }
            )
            return

        await page.wait_for_timeout(2000)
        await page.wait_for_selector('div.entry-list', timeout=20_000)
        article_links = await page.evaluate(
            """() => {
            const links = [];
            document.querySelectorAll('.entry-list a.jj-link.title[href*="/post/"]').forEach((a) => {
                links.push(new URL(a.getAttribute('href') || '', location.origin).href);
            });
            return [...new Set(links)];
        }"""
        )
        await context.add_requests(article_links[:10])

    @crawler.failed_request_handler
    async def on_failed(context: PlaywrightCrawlingContext, error: Exception) -> None:
        context.log.error(f'failed {context.request.url}: {error!s}'[:200])

    stats = await crawler.run(['https://juejin.cn/'])
    assert stats.requests_finished >= 1

    page_data = await crawler.get_data()
    items = page_data.items
    assert len(items) >= 1, 'Expected at least one pushed article row; site layout may have changed.'

    for row in items:
        assert 'url' in row
        assert '/post/' in str(row['url'])
        assert 'title' in row
        assert 'content' in row
        assert 'crawled_at' in row
