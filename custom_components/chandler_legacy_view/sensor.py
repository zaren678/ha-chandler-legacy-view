"""Sensor platform for Chandler Legacy View valves."""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

# Home Assistant does not currently expose a dedicated water hardness unit
# constant, so we keep using the unit string Chandler devices report.
WATER_HARDNESS_GRAINS_PER_GALLON = "grains_per_gallon"
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CONNECTION_MANAGER, DATA_DISCOVERY_MANAGER, DOMAIN
from .connection import ValveConnection, ValveConnectionManager
from .cycle import cycle_phase, cycle_remaining_seconds
from .dashboard import format_time_of_day
from .discovery import BLUETOOTH_LOST_CHANGES, ValveDiscoveryManager
from .entity import ChandlerValveEntity, _is_clack_valve
from .models import (
    ValveAdvancedSettingsData,
    ValveAdvertisement,
    ValveDashboardData,
    ValveHistoryData,
)
from .regeneration import regeneration_is_active

_LOGGER = logging.getLogger(__name__)


class ValveDashboardSensor(ChandlerValveEntity, SensorEntity):
    """Base class for sensors driven by dashboard packet updates."""

    _attr_available = True

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
        *,
        unique_id_suffix: str,
        name_suffix: str | None,
    ) -> None:
        super().__init__(advertisement)
        base_name = self._attr_name
        self._attr_unique_id = f"{advertisement.address}_{unique_id_suffix}"
        self._name_suffix = name_suffix
        self._remove_dashboard_listener: CALLBACK_TYPE | None = None
        self._attr_name = self._apply_name_suffix(base_name, advertisement)
        self._update_from_dashboard(connection.dashboard_data, write_state=False)
        self._remove_dashboard_listener = connection.add_dashboard_listener(
            self._handle_dashboard_update
        )

    def _apply_name_suffix(
        self, base_name: str, advertisement: ValveAdvertisement
    ) -> str:
        suffix = self._get_name_suffix(advertisement)
        if suffix:
            return f"{base_name} {suffix}"
        return base_name

    def _get_name_suffix(self, advertisement: ValveAdvertisement) -> str | None:
        """Return the display suffix for the entity name."""

        return self._name_suffix

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for this valve."""

        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._attr_available = True

        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store the most recent advertisement for the valve."""

        super().async_update_from_advertisement(advertisement)
        base_name = self._attr_name
        self._attr_name = self._apply_name_suffix(base_name, advertisement)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when the entity is removed."""

        await super().async_will_remove_from_hass()
        if self._remove_dashboard_listener is not None:
            self._remove_dashboard_listener()
            self._remove_dashboard_listener = None

    def _update_from_dashboard(
        self, dashboard: ValveDashboardData | None, *, write_state: bool
    ) -> None:
        """Update the native value from dashboard data."""

        self._attr_native_value = self._extract_native_value(dashboard)
        if write_state and self.hass is not None:
            self.async_write_ha_state()

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> object | None:
        """Return the sensor's value derived from dashboard data."""

        raise NotImplementedError

    @callback
    def _handle_dashboard_update(
        self, dashboard: ValveDashboardData | None
    ) -> None:
        """Handle updates from the dashboard poller."""

        self._update_from_dashboard(dashboard, write_state=True)


class ValvePresentFlowSensor(ValveDashboardSensor):
    """Represent the present flow rate reported by a valve dashboard packet."""

    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="present_flow",
            name_suffix="Present Flow",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> float | None:
        if dashboard is None:
            return None
        return dashboard.present_flow


class ValveWaterHardnessSensor(ValveDashboardSensor):
    """Represent the configured water hardness reported by a valve."""

    _attr_native_unit_of_measurement = WATER_HARDNESS_GRAINS_PER_GALLON
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="water_hardness",
            name_suffix="Water Hardness",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return dashboard.water_hardness


class ValveTimeOfDaySensor(ValveDashboardSensor):
    """Represent the valve's local clock as a literal time value."""

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="time_of_day",
            name_suffix="Time of Day",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> str | None:
        if dashboard is None:
            return None
        return format_time_of_day(
            dashboard.time_hour, dashboard.time_minute, dashboard.is_pm
        )


class ValveBatteryCapacitySensor(ValveDashboardSensor):
    """Represent the battery capacity reported by a non-Clack valve."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="battery",
            name_suffix="Battery",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return dashboard.battery_capacity


class ValveSoftWaterRemainingSensor(ValveDashboardSensor):
    """Represent the soft water remaining until regeneration for metered valves."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="soft_water_remaining",
            name_suffix="Soft Water Remaining",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return dashboard.water_remaining_until_regeneration


class ValveDaysUntilRegenerationSensor(ValveDashboardSensor):
    """Represent the countdown until the next scheduled regeneration."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="days_until_regeneration",
            name_suffix=None,
        )

    def _get_name_suffix(self, advertisement: ValveAdvertisement) -> str | None:
        if advertisement.valve_type == "TimeClockSoftener":
            return "Days Until Regeneration"
        return "Days Until Backwash"

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return dashboard.air_recharge


class ValveWaterUsageTodaySensor(ValveDashboardSensor):
    """Represent the total water usage recorded for the current day."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="water_usage_today",
            name_suffix="Water Usage Today",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return dashboard.water_usage


class ValvePeakFlowTodaySensor(ValveDashboardSensor):
    """Represent the peak flow recorded for the current day."""

    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="peak_flow_today",
            name_suffix="Peak Flow Today",
        )

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> float | None:
        if dashboard is None:
            return None
        return dashboard.peak_flow


class ValveCycleRemainingSensor(ValveDashboardSensor):
    """Represent seconds remaining in the current cycle phase."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="cycle_remaining",
            name_suffix=None,
        )

    def _get_name_suffix(self, advertisement: ValveAdvertisement) -> str | None:
        if advertisement.is_metered_softener or (
            advertisement.valve_type == "TimeClockSoftener"
        ):
            return "Regeneration Remaining"
        return "Backwash Remaining"

    def _extract_native_value(
        self, dashboard: ValveDashboardData | None
    ) -> int | None:
        if dashboard is None:
            return None
        return cycle_remaining_seconds(
            regeneration_is_active(
                dashboard.regen_active, dashboard.prefill_soak_mode
            ),
            dashboard.pos_time,
            dashboard.pos_option_seconds,
        )


class ValveCycleStateSensor(ValveDashboardSensor):
    """Represent the current regeneration or backwash cycle phase."""

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        self._dashboard: ValveDashboardData | None = None
        super().__init__(
            advertisement,
            connection,
            unique_id_suffix="cycle_state",
            name_suffix=None,
        )

    def _get_name_suffix(self, advertisement: ValveAdvertisement) -> str | None:
        if advertisement.is_metered_softener or (
            advertisement.valve_type == "TimeClockSoftener"
        ):
            return "Regeneration State"
        return "Backwash State"

    def _update_from_dashboard(
        self, dashboard: ValveDashboardData | None, *, write_state: bool
    ) -> None:
        self._dashboard = dashboard
        super()._update_from_dashboard(dashboard, write_state=write_state)

    def _extract_native_value(self, dashboard: ValveDashboardData | None) -> str | None:
        if dashboard is None:
            return None
        return cycle_phase(
            regeneration_is_active(
                dashboard.regen_active, dashboard.prefill_soak_mode
            ),
            dashboard.regen_cycle_position,
        )

    @property
    def extra_state_attributes(self) -> dict[str, int | bool | None]:
        """Expose raw cycle state and timing for diagnostics and automations."""

        dashboard = self._dashboard
        if dashboard is None:
            return {}
        return {
            "active": regeneration_is_active(
                dashboard.regen_active, dashboard.prefill_soak_mode
            ),
            "regen_active_raw": dashboard.regen_active,
            "prefill_soak_mode": dashboard.prefill_soak_mode,
            "position": dashboard.regen_cycle_position,
            "remaining_seconds": cycle_remaining_seconds(
                regeneration_is_active(
                    dashboard.regen_active, dashboard.prefill_soak_mode
                ),
                dashboard.pos_time,
                dashboard.pos_option_seconds,
            ),
            "remaining_time_raw": dashboard.pos_time,
            "seconds_mode_raw": dashboard.pos_option_seconds,
            "position_time": dashboard.pos_time,
        }


class ValveRegenPositionSensor(ChandlerValveEntity, SensorEntity):
    """Expose a single regen cycle stage duration from Advanced Settings (read-only)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    # App display names per valve family (from CsAdvancedSettingsViewModel.java).
    # Aeration/Nitro filter family is the common Evb019 case (your CS_Aeration_Fltr):
    # P1 decompress (s), P2 air release (s), P3 backwash (min), P4 rest (min),
    # P5 air draw (min), P6 rapid rinse (min). Positions 7-8 unused.
    _AERATION_POSITION_NAMES: tuple[str, ...] = (
        "Decompress",
        "Air Release",
        "Backwash",
        "Rest",
        "Air Draw",
        "Rapid Rinse",
        "Position 7",
        "Position 8",
    )
    _AERATION_POSITION_UNITS: tuple[str, ...] = (
        UnitOfTime.SECONDS,
        UnitOfTime.SECONDS,
        UnitOfTime.MINUTES,
        UnitOfTime.MINUTES,
        UnitOfTime.MINUTES,
        UnitOfTime.MINUTES,
        UnitOfTime.MINUTES,
        UnitOfTime.MINUTES,
    )

    def _is_aeration_valve(self, adv: ValveAdvertisement | None) -> bool:
        if adv is None:
            return False
        vt = adv.valve_type
        return vt in (
            "NitroFilter",
            "Sidekick",
            "CommercialAeration",
            "CenturionNitroSidekick",
            "CenturionNitroSidekickV3",
            "NitroPro",
            "NitroProSidekick",
        ) or (vt is None and adv.model in (None, "Evb019"))

    def _position_display_name(self, adv: ValveAdvertisement | None) -> str:
        # For aeration family, use app titles; otherwise generic fallback with
        # cycle index so unique_id stays stable.
        if self._is_aeration_valve(adv):
            try:
                return self._AERATION_POSITION_NAMES[self._position_index]
            except IndexError:
                pass
        return f"Regen Position {self._position_index+1}"

    def _position_unit(self, adv: ValveAdvertisement | None) -> str:
        if self._is_salt_dose():
            return "lb"
        if self._is_aeration_valve(adv):
            try:
                return self._AERATION_POSITION_UNITS[self._position_index]
            except IndexError:
                pass
        return UnitOfTime.MINUTES

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
        position_index: int,
    ) -> None:
        super().__init__(advertisement)
        self._connection = connection
        self._position_index = position_index  # 0-based, P1..P8 maps to 49-56
        self._attr_unique_id = f"{advertisement.address}_regen_pos_{position_index+1}"
        display = self._position_display_name(advertisement)
        self._attr_name = f"{self._attr_name} {display}"
        self._attr_available = False
        self._advanced_data: ValveAdvancedSettingsData | None = (
            connection.advanced_settings_data
        )
        self._is_evb019 = advertisement.model in (None, "Evb019")
        self._remove_listener: CALLBACK_TYPE | None = (
            connection.add_advanced_settings_listener(self._handle_advanced_update)
        )
        self._update_from_advanced_data(self._advanced_data)

    def _is_salt_dose(self) -> bool:
        adv = self._advertisement
        if adv is None:
            return False
        return (
            adv.valve_type in ("MeteredSoftener", "CommercialMeteredSoftener")
            or adv.is_twin_valve
        ) and self._position_index == 4

    def _update_from_advanced_data(
        self, data: ValveAdvancedSettingsData | None
    ) -> None:
        self._advanced_data = data
        if not self._is_evb019:
            self._attr_available = False
            self._attr_native_value = None
            return
        if data is None or len(data.positions) <= self._position_index:
            self._attr_available = False
            self._attr_native_value = None
            return
        # Read-only sensor: always available when data exists; adjustability is
        # exposed via `not_adjustable` attribute only.
        self._attr_available = True
        self._attr_native_unit_of_measurement = self._position_unit(self._advertisement)
        self._attr_native_value = data.positions[self._position_index]

    @callback
    def _handle_advanced_update(
        self, data: ValveAdvancedSettingsData | None
    ) -> None:
        self._update_from_advanced_data(data)
        if self.hass is not None:
            self.async_write_ha_state()

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._is_evb019 = advertisement.model in (None, "Evb019")
            self._update_from_advanced_data(self._connection.advanced_settings_data)
        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        super().async_update_from_advertisement(advertisement)
        display = self._position_display_name(advertisement)
        self._attr_name = f"{self._attr_name} {display}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self._connection.advanced_settings_data
        defaults = self._connection.advanced_settings_defaults
        attrs: dict[str, object] = {
            "position_index": self._position_index + 1,
            "position_name": self._position_display_name(self._advertisement),
        }
        if data is not None and len(data.positions) > self._position_index:
            attrs["position_value"] = data.positions[self._position_index]
        else:
            attrs["position_value"] = None
        if defaults is not None and len(defaults.positions) > self._position_index:
            attrs["default_value"] = defaults.positions[self._position_index]
        if data is not None and len(data.position_not_adjustable) > self._position_index:
            attrs["not_adjustable"] = data.position_not_adjustable[self._position_index]
        return attrs

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._remove_listener is not None:
            remover = self._remove_listener  # type: ignore[attr-defined]
            try:
                remover()  # type: ignore[call-arg]
            except Exception:
                pass
            self._remove_listener = None


class ValveHistorySensor(ChandlerValveEntity, SensorEntity):
    """Base for sensors driven by Status and History (119) — read-only, separate poll."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
        *,
        unique_id_suffix: str,
        name_suffix: str | None,
    ) -> None:
        super().__init__(advertisement)
        self._connection = connection
        base_name = self._attr_name
        self._attr_unique_id = f"{advertisement.address}_{unique_id_suffix}"
        self._name_suffix = name_suffix
        self._remove_history_listener: CALLBACK_TYPE | None = None
        self._attr_name = self._apply_name_suffix(base_name, advertisement)
        self._is_evb019 = advertisement.model in (None, "Evb019")
        self._attr_available = False
        self._update_from_history(connection.history_data, write_state=False)
        self._remove_history_listener = connection.add_history_listener(self._handle_history_update)

    def _apply_name_suffix(self, base_name: str, advertisement: ValveAdvertisement) -> str:
        suffix = self._get_name_suffix(advertisement)
        if suffix:
            return f"{base_name} {suffix}"
        return base_name

    def _get_name_suffix(self, advertisement: ValveAdvertisement) -> str | None:
        return self._name_suffix

    @callback
    def async_handle_bluetooth_update(self, advertisement: ValveAdvertisement, change: BluetoothChange) -> None:
        if change in BLUETOOTH_LOST_CHANGES:
            self._attr_available = False
        else:
            self.async_update_from_advertisement(advertisement)
            self._is_evb019 = advertisement.model in (None, "Evb019")
            self._update_from_history(self._connection.history_data, write_state=False)
        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(self, advertisement: ValveAdvertisement) -> None:
        super().async_update_from_advertisement(advertisement)
        base_name = self._attr_name
        self._attr_name = self._apply_name_suffix(base_name, advertisement)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._remove_history_listener is not None:
            self._remove_history_listener()
            self._remove_history_listener = None

    def _update_from_history(self, data: ValveHistoryData | None, *, write_state: bool) -> None:
        self._attr_native_value = self._extract_native_value(data)
        # History is infrequent; mark unavailable until first successful fetch
        if not self._is_evb019:
            self._attr_available = False
        elif data is None or self._attr_native_value is None:
            self._attr_available = False
        else:
            self._attr_available = True
        if write_state and self.hass is not None:
            self.async_write_ha_state()

    def _extract_native_value(self, data: ValveHistoryData | None) -> object | None:
        raise NotImplementedError

    @callback
    def _handle_history_update(self, data: ValveHistoryData | None) -> None:
        self._update_from_history(data, write_state=True)


class ValveHistoryTotalGallonsSensor(ValveHistorySensor):
    """Total gallons from History (lifetime, not resettable)."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_total_gallons", name_suffix="History Total Gallons")

    def _extract_native_value(self, data: ValveHistoryData | None) -> int | None:
        return data.total_gallons if data else None


class ValveHistoryTotalGallonsResettableSensor(ValveHistorySensor):
    """Total gallons resettable from History."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_total_gallons_resettable", name_suffix="History Total Gallons Resettable")

    def _extract_native_value(self, data: ValveHistoryData | None) -> int | None:
        return data.total_gallons_resettable if data else None


class ValveHistoryRegenCounterSensor(ValveHistorySensor):
    """Regen count from History (lifetime)."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_regen_counter", name_suffix="History Regen Count")

    def _extract_native_value(self, data: ValveHistoryData | None) -> int | None:
        return data.regen_counter if data else None


class ValveHistoryRegenCounterResettableSensor(ValveHistorySensor):
    """Regen count resettable from History."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_regen_counter_resettable", name_suffix="History Regen Count Resettable")

    def _extract_native_value(self, data: ValveHistoryData | None) -> int | None:
        return data.regen_counter_resettable if data else None


class ValveHistoryWaterUsageDaySensor(ValveHistorySensor):
    """Exposes History water usage day graph (62 days) as attributes; state is latest day."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_water_usage_day", name_suffix="History Water Usage Day")

    def _extract_native_value(self, data: ValveHistoryData | None) -> float | None:
        if data and data.water_usage_day:
            # Latest (most recent) is last element after parsing
            return float(data.water_usage_day[-1])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self._connection.history_data if hasattr(self, "_connection") else None
        if data and data.water_usage_day:
            return {"water_usage_day": list(data.water_usage_day), "days": len(data.water_usage_day)}
        return {}


class ValveHistoryWaterUsageRegenSensor(ValveHistorySensor):
    """Per-regen water usage graph (42 regens) — state is latest regen."""

    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_water_usage_regen", name_suffix="History Water Usage Per Regen")

    def _extract_native_value(self, data: ValveHistoryData | None) -> float | None:
        if data and data.water_usage_regen:
            return float(data.water_usage_regen[-1])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self._connection.history_data if hasattr(self, "_connection") else None
        if data and data.water_usage_regen:
            return {"water_usage_regen": list(data.water_usage_regen), "count": len(data.water_usage_regen)}
        return {}


class ValveHistoryPeakFlowSensor(ValveHistorySensor):
    """Peak flow history graph (62 days) — state is latest peak."""

    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, advertisement: ValveAdvertisement, connection: ValveConnection) -> None:
        self._connection = connection
        super().__init__(advertisement, connection, unique_id_suffix="history_peak_flow", name_suffix="History Peak Flow")

    def _extract_native_value(self, data: ValveHistoryData | None) -> float | None:
        if data and data.peak_flow:
            return float(data.peak_flow[-1])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self._connection.history_data if hasattr(self, "_connection") else None
        if data and data.peak_flow:
            return {"peak_flow": list(data.peak_flow), "days": len(data.peak_flow)}
        return {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dashboard-driven sensors for Chandler valves."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    discovery_manager: ValveDiscoveryManager = entry_data[DATA_DISCOVERY_MANAGER]
    connection_manager: ValveConnectionManager = entry_data[DATA_CONNECTION_MANAGER]

    flow_entities: dict[str, ValvePresentFlowSensor] = {}
    hardness_entities: dict[str, ValveWaterHardnessSensor] = {}
    time_entities: dict[str, ValveTimeOfDaySensor] = {}
    battery_entities: dict[str, ValveBatteryCapacitySensor] = {}
    soft_water_entities: dict[str, ValveSoftWaterRemainingSensor] = {}
    days_entities: dict[str, ValveDaysUntilRegenerationSensor] = {}
    usage_entities: dict[str, ValveWaterUsageTodaySensor] = {}
    peak_entities: dict[str, ValvePeakFlowTodaySensor] = {}
    cycle_entities: dict[str, ValveCycleStateSensor] = {}
    remaining_entities: dict[str, ValveCycleRemainingSensor] = {}
    regen_position_entities: dict[str, list[ValveRegenPositionSensor]] = {}
    history_total_entities: dict[str, ValveHistoryTotalGallonsSensor] = {}
    history_total_reset_entities: dict[str, ValveHistoryTotalGallonsResettableSensor] = {}
    history_regen_entities: dict[str, ValveHistoryRegenCounterSensor] = {}
    history_regen_reset_entities: dict[str, ValveHistoryRegenCounterResettableSensor] = {}
    history_day_entities: dict[str, ValveHistoryWaterUsageDaySensor] = {}
    history_regen_usage_entities: dict[str, ValveHistoryWaterUsageRegenSensor] = {}
    history_peak_entities: dict[str, ValveHistoryPeakFlowSensor] = {}

    def _ensure_dashboard_entity(
        advertisement: ValveAdvertisement,
        entity_map: dict[str, ValveDashboardSensor],
        *,
        predicate: Callable[[ValveAdvertisement], bool] | None = None,
        factory: Callable[[ValveAdvertisement, ValveConnection], ValveDashboardSensor],
        debug_description: str,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        entity = entity_map.get(advertisement.address)
        new_entities: list[ValveDashboardSensor] = []

        if entity is None:
            if predicate is not None and not predicate(advertisement):
                return None, new_entities

            connection = connection_manager.get_connection(advertisement.address)
            if connection is None:
                _LOGGER.debug(
                    "Delaying %s sensor creation for %s; connection not ready",
                    debug_description,
                    advertisement.address,
                )
                return None, new_entities

            entity = factory(advertisement, connection)
            entity_map[advertisement.address] = entity
            new_entities.append(entity)

        return entity, new_entities

    def _ensure_flow_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            flow_entities,
            factory=lambda adv, conn: ValvePresentFlowSensor(adv, conn),
            debug_description="present flow",
        )

    def _ensure_hardness_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            hardness_entities,
            predicate=lambda adv: adv.is_metered_softener,
            factory=lambda adv, conn: ValveWaterHardnessSensor(adv, conn),
            debug_description="water hardness",
        )

    def _ensure_time_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            time_entities,
            factory=lambda adv, conn: ValveTimeOfDaySensor(adv, conn),
            debug_description="time of day",
        )

    def _ensure_battery_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            battery_entities,
            predicate=lambda adv: not _is_clack_valve(adv.name),
            factory=lambda adv, conn: ValveBatteryCapacitySensor(adv, conn),
            debug_description="battery",
        )

    def _ensure_soft_water_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            soft_water_entities,
            predicate=lambda adv: adv.is_metered_softener,
            factory=lambda adv, conn: ValveSoftWaterRemainingSensor(adv, conn),
            debug_description="soft water remaining",
        )

    def _ensure_days_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            days_entities,
            predicate=lambda adv: not adv.is_metered_softener,
            factory=lambda adv, conn: ValveDaysUntilRegenerationSensor(adv, conn),
            debug_description="days until regeneration",
        )

    def _ensure_usage_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            usage_entities,
            factory=lambda adv, conn: ValveWaterUsageTodaySensor(adv, conn),
            debug_description="water usage today",
        )

    def _ensure_peak_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            peak_entities,
            factory=lambda adv, conn: ValvePeakFlowTodaySensor(adv, conn),
            debug_description="peak flow today",
        )

    def _ensure_cycle_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            cycle_entities,
            factory=lambda adv, conn: ValveCycleStateSensor(adv, conn),
            debug_description="cycle state",
        )

    def _ensure_remaining_entity(
        advertisement: ValveAdvertisement,
    ) -> tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]]:
        return _ensure_dashboard_entity(
            advertisement,
            remaining_entities,
            factory=lambda adv, conn: ValveCycleRemainingSensor(adv, conn),
            debug_description="cycle remaining",
        )

    def _ensure_regen_position_entities(
        advertisement: ValveAdvertisement,
    ) -> list[ValveRegenPositionSensor]:
        # Only Evb019 supports Advanced Settings position buffers; gate by model
        if advertisement.model not in (None, "Evb019"):
            return []
        existing = regen_position_entities.get(advertisement.address)
        if existing is not None:
            return []
        connection = connection_manager.get_connection(advertisement.address)
        if connection is None:
            _LOGGER.debug(
                "Delaying regen position sensor creation for %s; connection not ready",
                advertisement.address,
            )
            return []
        created: list[ValveRegenPositionSensor] = []
        for idx in range(8):
            ent = ValveRegenPositionSensor(advertisement, connection, idx)
            created.append(ent)
        regen_position_entities[advertisement.address] = created
        return created

    def _ensure_history_entity(
        advertisement: ValveAdvertisement,
        entity_map: dict[str, ValveHistorySensor],
        factory: Callable[[ValveAdvertisement, ValveConnection], ValveHistorySensor],
        debug_description: str,
    ) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        if advertisement.model not in (None, "Evb019"):
            return None, []
        entity = entity_map.get(advertisement.address)
        new_entities: list[ValveHistorySensor] = []
        if entity is None:
            connection = connection_manager.get_connection(advertisement.address)
            if connection is None:
                _LOGGER.debug("Delaying %s sensor creation for %s; connection not ready", debug_description, advertisement.address)
                return None, new_entities
            entity = factory(advertisement, connection)
            entity_map[advertisement.address] = entity
            new_entities.append(entity)
        return entity, new_entities

    def _ensure_history_total_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_total_entities, lambda adv, conn: ValveHistoryTotalGallonsSensor(adv, conn), "history total gallons")

    def _ensure_history_total_reset_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_total_reset_entities, lambda adv, conn: ValveHistoryTotalGallonsResettableSensor(adv, conn), "history total resettable")

    def _ensure_history_regen_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_regen_entities, lambda adv, conn: ValveHistoryRegenCounterSensor(adv, conn), "history regen counter")

    def _ensure_history_regen_reset_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_regen_reset_entities, lambda adv, conn: ValveHistoryRegenCounterResettableSensor(adv, conn), "history regen resettable")

    def _ensure_history_day_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_day_entities, lambda adv, conn: ValveHistoryWaterUsageDaySensor(adv, conn), "history water day")

    def _ensure_history_regen_usage_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_regen_usage_entities, lambda adv, conn: ValveHistoryWaterUsageRegenSensor(adv, conn), "history water regen")

    def _ensure_history_peak_entity(advertisement: ValveAdvertisement) -> tuple[ValveHistorySensor | None, list[ValveHistorySensor]]:
        return _ensure_history_entity(advertisement, history_peak_entities, lambda adv, conn: ValveHistoryPeakFlowSensor(adv, conn), "history peak flow")

    EnsureCallback = Callable[
        [ValveAdvertisement],
        tuple[ValveDashboardSensor | None, list[ValveDashboardSensor]],
    ]

    ensure_callbacks: tuple[EnsureCallback, ...] = (
        _ensure_flow_entity,
        _ensure_hardness_entity,
        _ensure_time_entity,
        _ensure_battery_entity,
        _ensure_soft_water_entity,
        _ensure_days_entity,
        _ensure_usage_entity,
        _ensure_peak_entity,
        _ensure_cycle_entity,
        _ensure_remaining_entity,
    )

    EnsureHistoryCallback = Callable[
        [ValveAdvertisement],
        tuple[ValveHistorySensor | None, list[ValveHistorySensor]],
    ]

    ensure_history_callbacks: tuple[EnsureHistoryCallback, ...] = (
        _ensure_history_total_entity,
        _ensure_history_total_reset_entity,
        _ensure_history_regen_entity,
        _ensure_history_regen_reset_entity,
        _ensure_history_day_entity,
        _ensure_history_regen_usage_entity,
        _ensure_history_peak_entity,
    )

    initial_entities: list[SensorEntity] = []
    for advertisement in discovery_manager.devices.values():
        for ensure_callback in ensure_callbacks:
            _, created = ensure_callback(advertisement)
            initial_entities.extend(created)
        for ensure_cb in ensure_history_callbacks:
            _, created = ensure_cb(advertisement)
            initial_entities.extend(created)
        initial_entities.extend(_ensure_regen_position_entities(advertisement))

    if initial_entities:
        async_add_entities(initial_entities)

    entity_maps = (
        flow_entities,
        hardness_entities,
        time_entities,
        battery_entities,
        soft_water_entities,
        days_entities,
        usage_entities,
        peak_entities,
        cycle_entities,
        remaining_entities,
    )
    history_entity_maps = (
        history_total_entities,
        history_total_reset_entities,
        history_regen_entities,
        history_regen_reset_entities,
        history_day_entities,
        history_regen_usage_entities,
        history_peak_entities,
    )

    @callback
    def _handle_discovery(
        advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        if change in BLUETOOTH_LOST_CHANGES:
            for entity_map in entity_maps:
                entity = entity_map.get(advertisement.address)
                if entity is not None:
                    entity.async_handle_bluetooth_update(advertisement, change)
            for entity_map in history_entity_maps:
                entity = entity_map.get(advertisement.address)
                if entity is not None:
                    entity.async_handle_bluetooth_update(advertisement, change)
            for ent in regen_position_entities.get(advertisement.address, []):
                ent.async_handle_bluetooth_update(advertisement, change)
            return

        results = [ensure_callback(advertisement) for ensure_callback in ensure_callbacks]
        history_results = [ensure_cb(advertisement) for ensure_cb in ensure_history_callbacks]

        new_entities: list[SensorEntity] = []
        for _, created in results:
            new_entities.extend(created)
        for _, created in history_results:
            new_entities.extend(created)
        new_regen = _ensure_regen_position_entities(advertisement)
        new_entities.extend(new_regen)

        if new_entities:
            async_add_entities(new_entities)

        for entity, _ in results:
            if entity is not None:
                entity.async_handle_bluetooth_update(advertisement, change)
        for entity, _ in history_results:
            if entity is not None:
                entity.async_handle_bluetooth_update(advertisement, change)
        for ent in regen_position_entities.get(advertisement.address, []):
            ent.async_handle_bluetooth_update(advertisement, change)

    remove_listener = discovery_manager.async_add_listener(_handle_discovery)
    entry.async_on_unload(remove_listener)
