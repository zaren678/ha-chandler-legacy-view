"""Tests for Chandler regeneration cycle state."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "cycle.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_cycle", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_CYCLE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CYCLE)


class CyclePhaseTests(unittest.TestCase):
    """Verify regeneration cycle phase rendering."""

    def test_inactive_cycle_is_idle(self) -> None:
        self.assertEqual("Idle", _CYCLE.cycle_phase(0, 2))

    def test_position_one_is_decompress(self) -> None:
        self.assertEqual("Decompress (1)", _CYCLE.cycle_phase(1, 1))

    def test_position_two_is_air_release(self) -> None:
        self.assertEqual("Air Release (2)", _CYCLE.cycle_phase(1, 2))

    def test_position_three_is_backwash(self) -> None:
        self.assertEqual("Backwash (3)", _CYCLE.cycle_phase(1, 3))

    def test_position_five_is_air_draw(self) -> None:
        self.assertEqual("Air Draw (5)", _CYCLE.cycle_phase(1, 5))

    def test_position_six_is_rapid_rinse(self) -> None:
        self.assertEqual("Rapid Rinse (6)", _CYCLE.cycle_phase(1, 6))

    def test_unknown_active_position_remains_visible(self) -> None:
        self.assertEqual("Position 7", _CYCLE.cycle_phase(1, 7))

    def test_cycle_remaining_seconds(self) -> None:
        self.assertEqual(16, _CYCLE.cycle_remaining_seconds(1, 16))
        self.assertEqual(0, _CYCLE.cycle_remaining_seconds(0, 16))
        self.assertEqual(0, _CYCLE.cycle_remaining_seconds(1, -1))
