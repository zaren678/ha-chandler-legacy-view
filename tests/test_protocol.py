"""Tests for Chandler protocol selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "protocol.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_protocol", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_PROTOCOL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROTOCOL)


class ProtocolSelectionTests(unittest.TestCase):
    """Verify DeviceList password decoding selection."""

    def test_authentication_status_overrides_missing_firmware(self) -> None:
        for status in (0, 128):
            with self.subTest(status=status):
                self.assertFalse(
                    _PROTOCOL.should_use_classic_password_decode(
                        status=status,
                        is_twin_valve=False,
                        firmware_version=None,
                        has_connection_counter=False,
                    )
                )

    def test_unknown_status_preserves_classic_fallback(self) -> None:
        self.assertTrue(
            _PROTOCOL.should_use_classic_password_decode(
                status=112,
                is_twin_valve=False,
                firmware_version=None,
                has_connection_counter=False,
            )
        )

    def test_connection_counter_selects_authentication_decode(self) -> None:
        self.assertFalse(
            _PROTOCOL.should_use_classic_password_decode(
                status=112,
                is_twin_valve=False,
                firmware_version=None,
                has_connection_counter=True,
            )
        )

    def test_known_classic_firmware_uses_classic_decode(self) -> None:
        self.assertTrue(
            _PROTOCOL.should_use_classic_password_decode(
                status=112,
                is_twin_valve=False,
                firmware_version=418,
                has_connection_counter=False,
            )
        )
