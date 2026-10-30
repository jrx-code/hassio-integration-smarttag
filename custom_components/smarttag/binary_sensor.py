"""Obecność tagu w zasięgu Bluetooth HA."""

from __future__ import annotations

import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartTagConfigEntry
from .const import CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS
from .entity import SmartTagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SmartTagConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    away = entry.options.get(CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS)
    async_add_entities(
        SmartTagPresence(coordinator, dev_id, away) for dev_id in coordinator.known_device_ids()
    )


class SmartTagPresence(SmartTagEntity, BinarySensorEntity):
    """Włączony, gdy w ostatnich N sekundach jakiś skaner BLE widział tag."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, coordinator, device_id: str, away_seconds: int) -> None:
        super().__init__(coordinator, device_id, "presence")
        self._away = away_seconds

    @property
    def is_on(self) -> bool:
        seen = self.coordinator.sightings.get(self._device_id)
        return bool(seen and time.monotonic() - seen.monotonic < self._away)

    @property
    def extra_state_attributes(self) -> dict:
        seen = self.coordinator.sightings.get(self._device_id)
        if not seen:
            return {}
        return {
            "source": seen.source,
            "rssi": seen.rssi,
            "tag_state": seen.adv.state_name,
            "motion": seen.adv.motion,
            "seconds_ago": round(time.monotonic() - seen.monotonic),
        }
