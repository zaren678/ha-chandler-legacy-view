"""Tests for Chandler Dashboard presentation helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "dashboard.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_dashboard", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_DASHBOARD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DASHBOARD)


class DashboardPresentationTests(unittest.TestCase):
    """Verify Dashboard values are rendered as device-local values."""

    def test_formats_twelve_hour_time(self) -> None:
        self.assertEqual("9:12 PM", _DASHBOARD.format_time_of_day(9, 12, True))
        self.assertEqual("12:05 AM", _DASHBOARD.format_time_of_day(12, 5, False))

    def test_formats_twenty_four_hour_time(self) -> None:
        self.assertEqual("23:07", _DASHBOARD.format_time_of_day(23, 7, False))

    def test_rejects_invalid_time(self) -> None:
        self.assertIsNone(_DASHBOARD.format_time_of_day(24, 0, False))
        self.assertIsNone(_DASHBOARD.format_time_of_day(9, 60, False))
