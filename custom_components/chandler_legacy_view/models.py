"""Data models for the Chandler Legacy View integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

_METERED_SOFTENER_VALVE_TYPES = {
    "MeteredSoftener",
    "CommercialMeteredSoftener",
}


@dataclass(slots=True)
class ValveAdvertisement:
    """Representation of a Bluetooth advertisement emitted by a valve."""

    address: str
    name: str | None
    rssi: int | None
    manufacturer_data: Mapping[int, bytes]
    service_data: Mapping[str, bytes]
    firmware_major: int | None = None
    firmware_minor: int | None = None
    firmware_version: int | None = None
    model: str | None = None
    is_twin_valve: bool = False
    is_400_series: bool = False
    has_connection_counter: bool = False
    valve_data_parsed: bool = False
    manufacturer_data_complete: bool = True
    valve_status: int | None = None
    salt_sensor_status: int | None = None
    water_status: int | None = None
    bypass_status: int | None = None
    valve_error: int | None = None
    valve_error_raw: int | None = None
    valve_time_hours: int | None = None
    valve_time_minutes: int | None = None
    valve_type_full: int | None = None
    valve_type: str | None = None
    valve_series_version: int | None = None
    connection_counter: int | None = None
    bootloader_version: int | None = None
    radio_protocol_version: int | None = None
    authentication_required: bool = False

    @property
    def is_metered_softener(self) -> bool:
        """Return ``True`` if the advertisement describes a metered softener valve."""

        if self.is_twin_valve:
            return True

        valve_type = self.valve_type
        if valve_type is None:
            return False

        return valve_type in _METERED_SOFTENER_VALVE_TYPES


@dataclass(slots=True)
class ValveAdvancedSettingsData:
    """Parsed data returned by the EVB019 Advanced Settings request."""

    positions: tuple[int, ...]
    position_not_adjustable: tuple[bool, ...]
    regen_day_override: int | None = None
    reserve_capacity: int | None = None
    resin_grains_capacity: int | None = None
    air_recharge_frequency: int | None = None


@dataclass(slots=True)
class ValveHistoryData:
    """Parsed data returned by the EVB019 Status and History request (119)."""

    # Current status snapshot (packet 0)
    current_water_flow: float | None = None
    total_gallons: int | None = None
    total_gallons_resettable: int | None = None
    regen_counter: int | None = None
    regen_counter_resettable: int | None = None
    regen_active: int | None = None
    is_prefill_soak_mode: bool | None = None
    shutoff_setting: bool | None = None
    bypass_setting: bool | None = None
    shutoff_state: bool | None = None
    bypass_state: bool | None = None
    display_off: bool | None = None
    # Graphs (read-only, for diagnostics / history)
    water_usage_day: tuple[float, ...] | None = None  # 62 floats, *10 gal
    water_usage_regen: tuple[float, ...] | None = None  # 42 floats, gal per regen
    peak_flow: tuple[float, ...] | None = None  # 62 floats, GPM


@dataclass(slots=True)
class ValveDashboardData:
    """Parsed data returned by the EVB019 Dashboard request."""

    time_hour: int
    time_minute: int
    is_pm: bool
    battery_capacity: int
    present_flow: float
    water_remaining_until_regeneration: int
    water_usage: int
    peak_flow: float
    water_hardness: int
    regeneration_time_hour: int
    regeneration_time_is_pm: bool
    shutoff_setting_enabled: bool
    bypass_setting_enabled: bool
    shutoff_active: bool
    bypass_active: bool
    display_off: bool
    filter_backwash: int
    air_recharge: int
    pos_time: int
    pos_option_seconds: int
    regen_cycle_position: int
    regen_active: int
    prefill_soak_mode: bool
    soak_timer: int
    is_in_aeration: bool
    tank_in_service: int
    graph_usage_ten_gallons: tuple[int, ...]

