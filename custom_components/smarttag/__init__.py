"""Integracja Samsung Galaxy SmartTag."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .ble import SMARTTAG_SERVICE_UUID
from .const import PRESENCE_TICK
from .coordinator import SmartTagCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type SmartTagConfigEntry = ConfigEntry[SmartTagCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SmartTagConfigEntry) -> bool:
    """Start: pamięć podręczna, chmura, nasłuch BLE."""
    coordinator = SmartTagCoordinator(hass, entry)
    await coordinator.async_load_cache()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            coordinator.async_handle_bluetooth,
            bluetooth.BluetoothCallbackMatcher(service_data_uuid=SMARTTAG_SERVICE_UUID, connectable=False),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    # Odświeżanie obecności, żeby tag "wychodził" po czasie bez ramek.
    @callback
    def _tick(_now) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(async_track_time_interval(hass, _tick, PRESENCE_TICK))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: SmartTagConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SmartTagConfigEntry) -> bool:
    """Zatrzymanie."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
