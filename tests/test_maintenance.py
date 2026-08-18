"""Tests for periodic valve maintenance decisions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "maintenance.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_maintenance", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MAINTENANCE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MAINTENANCE)


class MaintenanceTests(unittest.TestCase):
    """Verify watchdog and clock-maintenance decisions."""

    def test_dashboard_requires_more_than_thirty_five_minutes(self) -> None:
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

        self.assertFalse(
            _MAINTENANCE.dashboard_is_stale(
                now - timedelta(minutes=35),
                now - timedelta(hours=1),
                now,
                timedelta(minutes=35),
            )
        )
        self.assertTrue(
            _MAINTENANCE.dashboard_is_stale(
                now - timedelta(minutes=35, seconds=1),
                now - timedelta(hours=1),
                now,
                timedelta(minutes=35),
            )
        )

    def test_dashboard_uses_startup_grace_without_a_success(self) -> None:
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

        self.assertFalse(
            _MAINTENANCE.dashboard_is_stale(
                None,
                now - timedelta(minutes=30),
                now,
                timedelta(minutes=35),
            )
        )
        self.assertTrue(
            _MAINTENANCE.dashboard_is_stale(
                None,
                now - timedelta(minutes=36),
                now,
                timedelta(minutes=35),
            )
        )

    def test_clock_drift_wraps_across_midnight(self) -> None:
        local_now = datetime(2026, 8, 17, 0, 2)

        self.assertEqual(
            4,
            _MAINTENANCE.clock_drift_minutes(11, 58, True, local_now),
        )

    def test_clock_drift_handles_noon_and_midnight(self) -> None:
        self.assertEqual(
            0,
            _MAINTENANCE.clock_drift_minutes(
                12,
                0,
                False,
                datetime(2026, 8, 17, 0, 0),
            ),
        )
        self.assertEqual(
            0,
            _MAINTENANCE.clock_drift_minutes(
                12,
                0,
                True,
                datetime(2026, 8, 17, 12, 0),
            ),
        )

    def test_clock_drift_rejects_invalid_values(self) -> None:
        self.assertIsNone(
            _MAINTENANCE.clock_drift_minutes(
                24,
                0,
                False,
                datetime(2026, 8, 17, 12, 0),
            )
        )

    def test_normalizes_watchdog_timeout(self) -> None:
        self.assertEqual(
            35,
            _MAINTENANCE.normalize_watchdog_timeout_minutes(None),
        )
        self.assertEqual(
            20,
            _MAINTENANCE.normalize_watchdog_timeout_minutes(5),
        )
        self.assertEqual(
            1440,
            _MAINTENANCE.normalize_watchdog_timeout_minutes(2000),
        )
        self.assertEqual(
            timedelta(minutes=45),
            _MAINTENANCE.watchdog_timeout_duration("45"),
        )


class RefreshAttemptTests(unittest.IsolatedAsyncioTestCase):
    """Verify bounded refresh retry behavior."""

    async def test_stops_after_first_success(self) -> None:
        attempts: list[int] = []
        delays: list[float] = []

        async def _refresh(attempt: int) -> bool:
            attempts.append(attempt)
            return attempt == 2

        async def _sleep(delay: float) -> None:
            delays.append(delay)

        result = await _MAINTENANCE.run_refresh_attempts(
            _refresh,
            sleep=_sleep,
        )

        self.assertEqual(2, result)
        self.assertEqual([1, 2], attempts)
        self.assertEqual([30], delays)

    async def test_returns_none_after_all_attempts_fail(self) -> None:
        attempts: list[int] = []
        delays: list[float] = []

        async def _refresh(attempt: int) -> bool:
            attempts.append(attempt)
            return False

        async def _sleep(delay: float) -> None:
            delays.append(delay)

        result = await _MAINTENANCE.run_refresh_attempts(
            _refresh,
            sleep=_sleep,
        )

        self.assertIsNone(result)
        self.assertEqual([1, 2, 3], attempts)
        self.assertEqual([30, 30], delays)


if __name__ == "__main__":
    unittest.main()
