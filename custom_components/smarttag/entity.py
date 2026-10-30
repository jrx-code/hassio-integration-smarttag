"""Bazowa encja SmartTaga."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartTagCoordinator


class SmartTagEntity(CoordinatorEntity[SmartTagCoordinator]):
    """Encja przypięta do jednego tagu."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartTagCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        info = (coordinator.data or {}).get(device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Samsung",
            name=coordinator.names.get(device_id, device_id),
            model=info.model if info else None,
        )

    @property
    def available(self) -> bool:
        return True
