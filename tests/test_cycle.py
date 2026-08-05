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

    def test_position_two_is_decompress(self) -> None:
        self.assertEqual("Decompress (2)", _CYCLE.cycle_phase(1, 2))

    def test_unknown_active_position_remains_visible(self) -> None:
        self.assertEqual("Position 7", _CYCLE.cycle_phase(1, 7))
