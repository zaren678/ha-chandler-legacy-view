"""Button platform for Chandler Legacy water system valves."""

from __future__ import annotations

import logging

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CONNECTION_MANAGER, DATA_DISCOVERY_MANAGER, DOMAIN
from .connection import ValveCommandError, ValveConnection, ValveConnectionManager
from .discovery import BLUETOOTH_LOST_CHANGES, ValveDiscoveryManager
from .entity import ChandlerValveEntity
from .models import ValveAdvertisement, ValveDashboardData
from .regeneration import regeneration_is_active

_LOGGER = logging.getLogger(__name__)


class ValveRegenerationButton(ChandlerValveEntity, ButtonEntity):
    """Start regeneration or advance an active regeneration step."""

    def __init__(
        self,
        advertisement: ValveAdvertisement,
        connection: ValveConnection,
        *,
        advance_current_cycle: bool,
    ) -> None:
        super().__init__(advertisement)
        self._connection = connection
        self._advance_current_cycle = advance_current_cycle
        self._bluetooth_available = True
        self._dashboard: ValveDashboardData | None = connection.dashboard_data
        suffix = "next_regeneration_step" if advance_current_cycle else "regenerate_now"
        self._label = (
            "Next Regeneration Step" if advance_current_cycle else "Regenerate Now"
        )
        self._attr_unique_id = f"{advertisement.address}_{suffix}"
        self._attr_name = f"{self._attr_name} {self._label}"
        self._remove_dashboard_listener: CALLBACK_TYPE | None = (
            connection.add_dashboard_listener(self._handle_dashboard_update)
        )
        self._update_available()

    def _update_available(self) -> None:
        dashboard = self._dashboard
        if not self._bluetooth_available or dashboard is None:
            self._attr_available = False
            return

        cycle_active = regeneration_is_active(
            dashboard.regen_active,
            dashboard.prefill_soak_mode,
        )
        self._attr_available = (
            cycle_active if self._advance_current_cycle else not cycle_active
        )

    @callback
    def _handle_dashboard_update(
        self, dashboard: ValveDashboardData | None
    ) -> None:
        self._dashboard = dashboard
        self._update_available()
        if self.hass is not None:
            self.async_write_ha_state()

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store updated discovery data without losing the action name."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} {self._label}"

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        self._bluetooth_available = change not in BLUETOOTH_LOST_CHANGES
        if self._bluetooth_available:
            self.async_update_from_advertisement(advertisement)
        self._update_available()
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the dashboard listener."""

        await super().async_will_remove_from_hass()
        if self._remove_dashboard_listener is not None:
            self._remove_dashboard_listener()
            self._remove_dashboard_listener = None

    async def async_press(self) -> None:
        """Send the guarded regeneration command."""

        try:
            await self._connection.async_regenerate(
                advance_current_cycle=self._advance_current_cycle
            )
        except ValveCommandError as exc:
            raise HomeAssistantError(str(exc)) from exc


class ValveRefreshButton(ChandlerValveEntity, ButtonEntity):
    """Immediately refresh authenticated valve dashboard data."""

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(advertisement)
        self._connection = connection
        self._label = "Refresh Now"
        self._attr_unique_id = f"{advertisement.address}_refresh_now"
        self._attr_name = f"{self._attr_name} {self._label}"
        self._attr_available = True

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store updated discovery data without losing the action name."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} {self._label}"

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        self._attr_available = change not in BLUETOOTH_LOST_CHANGES
        if self._attr_available:
            self.async_update_from_advertisement(advertisement)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_press(self) -> None:
        """Refresh dashboard data immediately."""

        try:
            await self._connection.async_refresh_now()
        except ValveCommandError as exc:
            raise HomeAssistantError(str(exc)) from exc


class ValveSyncTimeButton(ChandlerValveEntity, ButtonEntity):
    """Synchronize the valve clock with Home Assistant's local time."""

    def __init__(
        self, advertisement: ValveAdvertisement, connection: ValveConnection
    ) -> None:
        super().__init__(advertisement)
        self._connection = connection
        self._label = "Sync Time"
        self._attr_unique_id = f"{advertisement.address}_sync_time"
        self._attr_name = f"{self._attr_name} {self._label}"
        self._attr_available = advertisement.model in (None, "Evb019")

    def async_update_from_advertisement(
        self, advertisement: ValveAdvertisement
    ) -> None:
        """Store updated discovery data without losing the action name."""

        super().async_update_from_advertisement(advertisement)
        self._attr_name = f"{self._attr_name} {self._label}"

    @callback
    def async_handle_bluetooth_update(
        self, advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        """Handle Bluetooth discovery updates for the valve."""

        self._attr_available = (
            change not in BLUETOOTH_LOST_CHANGES
            and advertisement.model in (None, "Evb019")
        )
        if self._attr_available:
            self.async_update_from_advertisement(advertisement)
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_press(self) -> None:
        """Synchronize the valve clock."""

        try:
            await self._connection.async_sync_time()
        except ValveCommandError as exc:
            _LOGGER.warning(
                "Unable to synchronize valve %s clock: %s",
                self._connection.address,
                exc,
            )
            raise HomeAssistantError(str(exc)) from exc


ValveButton = ValveRegenerationButton | ValveRefreshButton | ValveSyncTimeButton


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up action buttons for Chandler valves."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    discovery_manager: ValveDiscoveryManager = entry_data[DATA_DISCOVERY_MANAGER]
    connection_manager: ValveConnectionManager = entry_data[DATA_CONNECTION_MANAGER]
    entities: dict[str, list[ValveButton]] = {}

    def _ensure_entities(
        advertisement: ValveAdvertisement,
    ) -> tuple[
        list[ValveButton] | None,
        list[ValveButton],
    ]:
        existing = entities.get(advertisement.address)
        if existing is not None:
            return existing, []

        connection = connection_manager.get_connection(advertisement.address)
        if connection is None:
            _LOGGER.debug(
                "Delaying regeneration button creation for %s; connection not ready",
                advertisement.address,
            )
            return None, []

        created: list[ValveButton] = [
            ValveRefreshButton(advertisement, connection),
            ValveSyncTimeButton(advertisement, connection),
            ValveRegenerationButton(
                advertisement, connection, advance_current_cycle=False
            ),
            ValveRegenerationButton(
                advertisement, connection, advance_current_cycle=True
            ),
        ]
        entities[advertisement.address] = created
        return created, list(created)

    initial_entities: list[ValveButton] = []
    for advertisement in discovery_manager.devices.values():
        _, created = _ensure_entities(advertisement)
        initial_entities.extend(created)
    if initial_entities:
        async_add_entities(initial_entities)

    @callback
    def _handle_discovery(
        advertisement: ValveAdvertisement, change: BluetoothChange
    ) -> None:
        pair = entities.get(advertisement.address)
        if pair is None and change not in BLUETOOTH_LOST_CHANGES:
            pair, created = _ensure_entities(advertisement)
            if created:
                async_add_entities(created)
        if pair is not None:
            for entity in pair:
                entity.async_handle_bluetooth_update(advertisement, change)

    remove_listener = discovery_manager.async_add_listener(_handle_discovery)
    entry.async_on_unload(remove_listener)
