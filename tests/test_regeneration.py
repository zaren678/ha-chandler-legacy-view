"""Tests for Chandler regeneration commands and state."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "regeneration.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_regeneration", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_REGENERATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_REGENERATION)


class RegenerationTests(unittest.TestCase):
    """Verify regeneration state and command payloads."""

    def test_regen_now_payload_matches_captured_mobile_command(self) -> None:
        self.assertEqual(
            "75757575757575757575757575524e7575757575",
            _REGENERATION.create_regen_now_payload().hex(),
        )

    def test_normal_active_flag_marks_regeneration_active(self) -> None:
        self.assertTrue(_REGENERATION.regeneration_is_active(1, False))

    def test_prefill_soak_marks_regeneration_active(self) -> None:
        self.assertTrue(_REGENERATION.regeneration_is_active(0, True))

    def test_idle_state_is_not_active(self) -> None:
        self.assertFalse(_REGENERATION.regeneration_is_active(0, False))
