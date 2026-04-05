"""Playwright crawl of news.baidu.com — Python equivalent of the JS PlaywrightCrawler snippet.

Requirements (local or platform worker image):

    crawlee[playwright]
    playwright>=1.27.0

Then install browsers once: ``playwright install chromium``
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from crawlee import ConcurrencySettings
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

START_URLS = ['https://news.baidu.com/']

# Same logic as page.$$eval('a[href]', ...) in JavaScript.
_LINKS_IN_PAGE_JS = """
() => {
  const anchors = Array.from(document.querySelectorAll('a[href]'));
  return anchors
    .map((a) => ({
      text: (a.innerText || '').trim().slice(0, 80),
      href: a.href,
    }))
    .filter((x) => x.text && x.href.startsWith('http'))
    .slice(0, 40);
}
"""


async def main() -> None:
    crawler = PlaywrightCrawler(
        headless=True,
        max_requests_per_crawl=1,
        concurrency_settings=ConcurrencySettings(min_concurrency=1, max_concurrency=1, desired_concurrency=1),
        request_handler_timeout=timedelta(seconds=60),
        goto_options={'wait_until': 'domcontentloaded'},
    )

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        # Crawlee already navigated to context.request.url using goto_options above.
        await asyncio.sleep(2)

        page = context.page
        title = await page.title()
        context.log.info(f'页面标题: {title}')

        links: list[dict[str, str]] = await page.evaluate(_LINKS_IN_PAGE_JS)
        context.log.info(f'采集到约 {len(links)} 条链接（示例）')

        preview = {'title': title, 'sample': links[:15]}
        context.log.info(json.dumps(preview, ensure_ascii=False, indent=2))

        await context.push_data(
            {
                'url': context.request.url,
                'title': title,
                'links_sample': links[:15],
                'link_count': len(links),
            }
        )

    @crawler.failed_request_handler
    async def failed_request_handler(context: PlaywrightCrawlingContext, error: Exception) -> None:
        context.log.error(f'请求失败 {context.request.url}: {error}')

    await crawler.run(START_URLS)


if __name__ == '__main__':
    asyncio.run(main())
