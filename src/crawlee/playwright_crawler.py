"""Compatibility shim for mistaken imports such as ``from crawlee.playwright_crawler import ...``.

Prefer public imports::

    from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
"""

from __future__ import annotations

from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

__all__ = ['PlaywrightCrawler', 'PlaywrightCrawlingContext']
