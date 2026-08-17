"""Tests for Chandler valve clock commands."""

from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "clock.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_clock", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_CLOCK = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CLOCK)


class ClockTests(unittest.TestCase):
    """Verify Set Time command payloads."""

    def test_morning_payload_matches_mobile_app_layout(self) -> None:
        payload = _CLOCK.create_set_time_payload(datetime(2026, 8, 16, 9, 7, 5))

        self.assertEqual(20, len(payload))
        self.assertEqual([84, 9, 7, 0, 5], list(payload[13:18]))
        self.assertEqual("7575757575757575757575757554090700057575", payload.hex())

    def test_midnight_is_twelve_am(self) -> None:
        payload = _CLOCK.create_set_time_payload(datetime(2026, 8, 16, 0, 1, 2))

        self.assertEqual([84, 12, 1, 0, 2], list(payload[13:18]))

    def test_noon_is_twelve_pm(self) -> None:
        payload = _CLOCK.create_set_time_payload(datetime(2026, 8, 16, 12, 34, 56))

        self.assertEqual([84, 12, 34, 1, 56], list(payload[13:18]))

    def test_evening_uses_twelve_hour_clock(self) -> None:
        payload = _CLOCK.create_set_time_payload(datetime(2026, 8, 16, 23, 59, 58))

        self.assertEqual([84, 11, 59, 1, 58], list(payload[13:18]))
