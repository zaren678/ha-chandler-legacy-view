"""Tests for Chandler persistent polling configuration."""

from __future__ import annotations

import importlib.util
from enum import Enum
from pathlib import Path
import sys
import types
import unittest


class _Platform(Enum):
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    NUMBER = "number"
    SENSOR = "sensor"
    SWITCH = "switch"


homeassistant = types.ModuleType("homeassistant")
homeassistant_const = types.ModuleType("homeassistant.const")
homeassistant_const.Platform = _Platform
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.const", homeassistant_const)

_PACKAGE = "custom_components.chandler_legacy_view"
_ROOT = Path(__file__).parents[1] / "custom_components" / "chandler_legacy_view"
package = types.ModuleType(_PACKAGE)
package.__path__ = [str(_ROOT)]
sys.modules.setdefault(_PACKAGE, package)

for module_name in ("const", "polling"):
    qualified_name = f"{_PACKAGE}.{module_name}"
    spec = importlib.util.spec_from_file_location(
        qualified_name, _ROOT / f"{module_name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)

_POLLING = sys.modules[f"{_PACKAGE}.polling"]


class PollingConfigurationTests(unittest.TestCase):
    """Verify persistent polling interval normalization."""

    def test_preserves_supported_interval(self) -> None:
        self.assertEqual(2.0, _POLLING.normalize_persistent_poll_interval(2))

    def test_clamps_interval_to_valve_idle_timeout_range(self) -> None:
        self.assertEqual(1.0, _POLLING.normalize_persistent_poll_interval(0))
        self.assertEqual(4.0, _POLLING.normalize_persistent_poll_interval(5))

    def test_invalid_interval_uses_default(self) -> None:
        self.assertEqual(4.0, _POLLING.normalize_persistent_poll_interval("bad"))

    def test_reads_per_valve_interval(self) -> None:
        self.assertEqual(
            2.0,
            _POLLING.persistent_poll_interval_for_address(
                {"first": 2, "second": 3}, "first"
            ),
        )
        self.assertEqual(
            4.0,
            _POLLING.persistent_poll_interval_for_address("invalid", "first"),
        )

    def test_updates_one_valve_without_losing_others(self) -> None:
        self.assertEqual(
            {"first": 4.0, "second": 3},
            _POLLING.updated_persistent_poll_intervals(
                {"first": 2, "second": 3}, "first", 5
            ),
        )
