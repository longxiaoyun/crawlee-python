"""Legacy import path ``crawlee.playwright_crawler`` (LLM mistakes)."""

import pytest

pytest.importorskip('playwright')

from crawlee.crawlers import PlaywrightCrawler as DirectCrawler
from crawlee.crawlers import PlaywrightCrawlingContext as DirectCtx
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext


def test_shim_reexports_playwright_symbols() -> None:
    assert PlaywrightCrawler is DirectCrawler
    assert PlaywrightCrawlingContext is DirectCtx
