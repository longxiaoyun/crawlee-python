"""Tests for :class:`crawlee.ConcurrencySettings`."""

from __future__ import annotations

import pytest

from crawlee import ConcurrencySettings


def test_default_desired_clamps_to_max_when_max_below_ten() -> None:
    """Omitted desired_concurrency must not default to 10 when max_concurrency is smaller."""
    s = ConcurrencySettings(min_concurrency=1, max_concurrency=2)
    assert s.desired_concurrency == 2
    assert s.min_concurrency == 1
    assert s.max_concurrency == 2


def test_default_desired_is_ten_when_range_allows() -> None:
    s = ConcurrencySettings(min_concurrency=1, max_concurrency=100)
    assert s.desired_concurrency == 10


def test_explicit_desired_still_validated() -> None:
    with pytest.raises(ValueError, match='greater than max_concurrency'):
        ConcurrencySettings(min_concurrency=1, max_concurrency=2, desired_concurrency=10)
