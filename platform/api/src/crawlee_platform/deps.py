"""Shared FastAPI dependencies."""

from functools import lru_cache

from crawlee_platform.config import Settings


@lru_cache(maxsize=1)
def get_settings_cached() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Return settings (cached in production; override in tests via lru_cache clear)."""
    return get_settings_cached()
