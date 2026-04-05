"""Juejin sample: home, article list, post detail; rows go to the default Dataset.

Run locally::

    cd /path/to/crawlee-python
    uv sync --extra playwright --extra beautifulsoup
    uv run playwright install chromium
    uv run python examples/juejin_playwright_sample.py

Visible browser (non-headless)::

    JUEJIN_HEADLESS=0 uv run python examples/juejin_playwright_sample.py

After a run, see ``storage/datasets/default/`` under the process cwd, plus Crawlee log lines.

You may parse the rendered HTML with BeautifulSoup (``page.content()``) or with
``page.evaluate(...)`` in the browser; both are valid. If you use BS4, install
the optional extra so ``from bs4 import BeautifulSoup`` resolves.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlee import ConcurrencySettings
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

START_URL = 'https://juejin.cn/'


async def main() -> None:
    """Run the Playwright crawl and print a short summary to the crawler log."""
    headless = os.environ.get('JUEJIN_HEADLESS', '1').lower() not in ('0', 'false', 'no')

    crawler = PlaywrightCrawler(
        headless=headless,
        max_requests_per_crawl=50,
        concurrency_settings=ConcurrencySettings(
            min_concurrency=1,
            max_concurrency=2,
            desired_concurrency=2,
        ),
        request_handler_timeout=timedelta(seconds=60),
        goto_options={'wait_until': 'networkidle', 'timeout': 30000},
    )

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        page = context.page
        url = context.request.url

        if '/post/' in url:
            await page.wait_for_timeout(1500)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            title_tag = soup.find('h1', attrs={'class': 'article-title'})
            if not title_tag:
                context.log.warning('title not found in HTML')
                return
            title = title_tag.get_text(strip=True)
            content = ''
            article_tag = soup.find('div', id='article-root')
            if article_tag:
                content = article_tag.get_text(strip=True)
            time_tag = soup.find('time', attrs={'class': 'time'})
            published_at = ''
            if time_tag:
                published_at = time_tag.get('datetime')

            await context.push_data(
                {
                    'url': url,
                    'title': title,
                    'content': content,
                    'published_at': published_at,
                    'crawled_at': datetime.now(timezone.utc).isoformat(),
                }
            )
            return

        await page.wait_for_timeout(1500)
        await page.wait_for_selector('div.entry-list', timeout=20_000)
        soup = BeautifulSoup(await page.content(), 'html.parser')
        entry_list = soup.find('div', attrs={'name': 'entry-list'}) or soup.select_one('div.entry-list')
        if not entry_list:
            context.log.warning('entry list not found in HTML')
            return

        hrefs: list[str] = []
        for title_row in entry_list.find_all('div', class_='title-row'):
            a_tag = title_row.find('a', href=True)
            if not a_tag:
                continue
            href = a_tag['href']
            if '/post/' not in href:
                continue
            hrefs.append(urljoin(url, href))

        # add_requests expects a sequence of URLs/str — never pass a single str (it iterates characters).
        await context.add_requests(hrefs[:10])

    @crawler.failed_request_handler
    async def on_failed(context: PlaywrightCrawlingContext, error: Exception) -> None:
        context.log.error(f'failed {context.request.url}: {error!s}'[:200])

    stats = await crawler.run([START_URL])
    crawler.log.info('Finished: requests_finished=%s', stats.requests_finished)

    page_data = await crawler.get_data()
    crawler.log.info('Dataset items count: %s', len(page_data.items))
    for i, row in enumerate(page_data.items[:5]):
        title = str(row.get('title', ''))[:60]
        crawler.log.info('  [%s] %r ...', i, title)


if __name__ == '__main__':
    asyncio.run(main())
