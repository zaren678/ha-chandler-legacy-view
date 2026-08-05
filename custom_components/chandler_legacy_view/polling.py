"""Helpers for Chandler persistent polling configuration."""

from __future__ import annotations

from collections.abc import Mapping

from .const import (
    DEFAULT_PERSISTENT_POLL_INTERVAL_SECONDS,
    MAX_PERSISTENT_POLL_INTERVAL_SECONDS,
    MIN_PERSISTENT_POLL_INTERVAL_SECONDS,
)


def normalize_persistent_poll_interval(value: object) -> float:
    """Return a supported persistent polling interval in seconds."""

    try:
        interval = float(value)
    except (TypeError, ValueError):
        interval = DEFAULT_PERSISTENT_POLL_INTERVAL_SECONDS

    return max(
        MIN_PERSISTENT_POLL_INTERVAL_SECONDS,
        min(interval, MAX_PERSISTENT_POLL_INTERVAL_SECONDS),
    )


def persistent_poll_interval_for_address(
    stored_intervals: object, address: str
) -> float:
    """Return the normalized stored interval for a valve address."""

    if not isinstance(stored_intervals, Mapping):
        return normalize_persistent_poll_interval(None)
    return normalize_persistent_poll_interval(stored_intervals.get(address))


def updated_persistent_poll_intervals(
    stored_intervals: object, address: str, value: object
) -> dict[str, float | object]:
    """Return stored per-valve intervals with one normalized update."""

    intervals = dict(stored_intervals) if isinstance(stored_intervals, Mapping) else {}
    intervals[address] = normalize_persistent_poll_interval(value)
    return intervals
