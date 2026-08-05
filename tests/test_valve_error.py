"""Tests for Chandler valve error decoding."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "valve_error.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_valve_error", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_VALVE_ERROR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_VALVE_ERROR)


class ValveErrorTests(unittest.TestCase):
    """Verify APK-derived valve error mappings and fail-safe behavior."""

    def test_decodes_official_evb019_bit_values(self) -> None:
        expected = {0: 0, 1: 2, 2: 3, 4: 4, 8: 5, 16: 6, 32: 7}
        for raw_code, error_code in expected.items():
            with self.subTest(raw_code=raw_code):
                self.assertEqual(
                    error_code,
                    _VALVE_ERROR.decode_evb019_valve_error(raw_code),
                )

    def test_unknown_evb019_value_remains_a_problem(self) -> None:
        error_code = _VALVE_ERROR.decode_evb019_valve_error(3)

        self.assertEqual(0, error_code)
        self.assertTrue(_VALVE_ERROR.valve_error_active(error_code, 3))
        self.assertEqual(
            "Unknown valve error (raw code 3)",
            _VALVE_ERROR.valve_error_display(error_code, False, 3),
        )

    def test_no_error_is_not_a_problem(self) -> None:
        self.assertFalse(_VALVE_ERROR.valve_error_active(0, 0))
        self.assertIsNone(_VALVE_ERROR.valve_error_active(None, None))

    def test_reports_apk_power_debounced_value(self) -> None:
        self.assertTrue(_VALVE_ERROR.valve_error_active(193, 193))
        self.assertEqual(
            "Power debounced, if this happens frequently, check power supply",
            _VALVE_ERROR.valve_error_display(193, False, 193),
        )

    def test_unknown_decoded_error_has_a_readable_fallback(self) -> None:
        self.assertTrue(_VALVE_ERROR.valve_error_active(42, None))
        self.assertEqual(
            "Unknown valve error (code 42)",
            _VALVE_ERROR.valve_error_display(42, False),
        )
