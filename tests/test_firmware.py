"""Tests for Chandler firmware version decoding."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chandler_legacy_view"
    / "firmware.py"
)
_SPEC = importlib.util.spec_from_file_location("chandler_firmware", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_FIRMWARE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIRMWARE)


class FirmwareDecodingTests(unittest.TestCase):
    """Verify firmware bytes used for model classification."""

    def test_decodes_c_prefixed_evb019_firmware(self) -> None:
        version = _FIRMWARE.decode_firmware_version(0xC5, 0x63)

        self.assertEqual((5, 63, 563), version)
        self.assertEqual("Evb019", _FIRMWARE.firmware_model(version[2]))

    def test_decodes_c_prefixed_evb034_firmware(self) -> None:
        version = _FIRMWARE.decode_firmware_version(0xC6, 0x18)

        self.assertEqual((6, 18, 618), version)
        self.assertEqual("Evb034", _FIRMWARE.firmware_model(version[2]))

    def test_decodes_d_prefixed_twin_firmware(self) -> None:
        self.assertEqual((1, 23, 123), _FIRMWARE.decode_firmware_version(0xD1, 0x23))

    def test_decodes_regular_bcd_components(self) -> None:
        self.assertEqual((4, 12, 412), _FIRMWARE.decode_firmware_version(0x04, 0x12))

    def test_preserves_unknown_non_decimal_component(self) -> None:
        self.assertEqual(0xAF, _FIRMWARE.decode_firmware_number(0xAF))

    def test_only_applies_prefix_handling_to_major_byte(self) -> None:
        self.assertEqual(0xC5, _FIRMWARE.decode_firmware_number(0xC5))
