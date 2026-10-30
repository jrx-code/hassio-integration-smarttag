"""Sensory: bateria, RSSI, stan tagu, ostatnie połączenie z chmury."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartTagConfigEntry
from .ble import TAG_STATES
from .const import BATTERY_PERCENT
from .entity import SmartTagEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SmartTagConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities = []
    for dev_id in coordinator.known_device_ids():
        entities += [
            SmartTagBattery(coordinator, dev_id),
            SmartTagRssi(coordinator, dev_id),
            SmartTagState(coordinator, dev_id),
            SmartTagLastConnection(coordinator, dev_id),
        ]
    async_add_entities(entities)


class SmartTagBattery(SmartTagEntity, SensorEntity):
    """Bateria: świeższa z BLE, inaczej z chmury. Samsung podaje tylko 4 poziomy."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "battery")

    @property
    def native_value(self) -> int | None:
        seen = self.coordinator.sightings.get(self._device_id)
        if seen:
            return BATTERY_PERCENT.get(seen.adv.battery)
        info = (self.coordinator.data or {}).get(self._device_id)
        return BATTERY_PERCENT.get(info.battery) if info and info.battery else None


class SmartTagRssi(SmartTagEntity, SensorEntity):
    """RSSI ostatniej ramki i skaner, który ją złapał."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "rssi")

    @property
    def native_value(self) -> int | None:
        seen = self.coordinator.sightings.get(self._device_id)
        return seen.rssi if seen else None

    @property
    def extra_state_attributes(self) -> dict:
        seen = self.coordinator.sightings.get(self._device_id)
        return {"source": seen.source} if seen else {}


class SmartTagState(SmartTagEntity, SensorEntity):
    """Stan z ramki BLE: przy właścicielu, zgubiony itd."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(TAG_STATES.values())

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "tag_state")

    @property
    def native_value(self) -> str | None:
        seen = self.coordinator.sightings.get(self._device_id)
        if not seen or seen.adv.state_name not in TAG_STATES.values():
            return None
        return seen.adv.state_name


class SmartTagLastConnection(SmartTagEntity, SensorEntity):
    """Z chmury: z którym telefonem tag był ostatnio połączony."""

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_connected_device")

    @property
    def native_value(self) -> str | None:
        info = (self.coordinator.data or {}).get(self._device_id)
        return info.connected_device if info else None

    @property
    def extra_state_attributes(self) -> dict:
        info = (self.coordinator.data or {}).get(self._device_id)
        if not info:
            return {}
        return {
            "d2d_status": info.d2d_status,
            "nearby": info.nearby,
            "last_connection": info.last_connection.isoformat() if info.last_connection else None,
            "searching_status": info.searching_status,
        }
