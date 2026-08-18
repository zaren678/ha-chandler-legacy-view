"""Pure helpers and timing defaults for valve maintenance."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

WATCHDOG_CHECK_INTERVAL = timedelta(minutes=5)
DEFAULT_WATCHDOG_TIMEOUT_MINUTES = 35
MIN_WATCHDOG_TIMEOUT_MINUTES = 20
MAX_WATCHDOG_TIMEOUT_MINUTES = 1440
RECOVERY_REFRESH_ATTEMPTS = 3
RECOVERY_REFRESH_RETRY_DELAY_SECONDS = 30

CLOCK_CHECK_INTERVAL = timedelta(hours=6)
CLOCK_DRIFT_LIMIT_MINUTES = 5


def normalize_watchdog_timeout_minutes(value: object) -> int:
    """Return a supported watchdog timeout in whole minutes."""

    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = DEFAULT_WATCHDOG_TIMEOUT_MINUTES
    return max(
        MIN_WATCHDOG_TIMEOUT_MINUTES,
        min(timeout, MAX_WATCHDOG_TIMEOUT_MINUTES),
    )


def watchdog_timeout_duration(value: object) -> timedelta:
    """Return the normalized watchdog timeout as a duration."""

    return timedelta(minutes=normalize_watchdog_timeout_minutes(value))


async def run_refresh_attempts(
    refresh: Callable[[int], Awaitable[bool]],
    *,
    attempts: int = RECOVERY_REFRESH_ATTEMPTS,
    retry_delay: float = RECOVERY_REFRESH_RETRY_DELAY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int | None:
    """Run bounded refresh attempts and return the successful attempt number."""

    for attempt in range(1, attempts + 1):
        if await refresh(attempt):
            return attempt
        if attempt < attempts:
            await sleep(retry_delay)
    return None


def dashboard_is_stale(
    last_success: datetime | None,
    monitoring_started: datetime,
    now: datetime,
    stale_after: timedelta,
) -> bool:
    """Return whether Dashboard data has exceeded the watchdog grace period."""

    reference = last_success or monitoring_started
    return now - reference > stale_after


def valve_clock_minutes(hour: int, minute: int, is_pm: bool) -> int | None:
    """Convert a valve clock value to minutes after midnight."""

    if not 0 <= hour < 24 or not 0 <= minute < 60:
        return None

    if hour > 12:
        return hour * 60 + minute

    hour_24 = hour % 12
    if is_pm:
        hour_24 += 12
    return hour_24 * 60 + minute


def clock_drift_minutes(
    valve_hour: int,
    valve_minute: int,
    valve_is_pm: bool,
    local_now: datetime,
) -> int | None:
    """Return the shortest absolute clock difference across midnight."""

    valve_minutes = valve_clock_minutes(
        valve_hour,
        valve_minute,
        valve_is_pm,
    )
    if valve_minutes is None:
        return None

    local_minutes = local_now.hour * 60 + local_now.minute
    difference = ((valve_minutes - local_minutes + 720) % 1440) - 720
    return abs(difference)
