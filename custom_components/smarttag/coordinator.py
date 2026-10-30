"""Koordynator: dane z chmury SmartThings + nasłuch BLE ramek FD5A."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartTagApiError, SmartTagAuthError, SmartThingsClient
from .ble import SMARTTAG_SERVICE_UUID, TagAdvertisement, parse_service_data
from .cloud import TagInfo, parse_tag
from .const import (
    CLOUD_INTERVAL,
    CONF_PAT,
    CONF_TOKEN_SOURCE,
    DOMAIN,
    SOURCE_PAT,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .privacy import pool_from_device

_LOGGER = logging.getLogger(__name__)


@dataclass
class BleSighting:
    """Ostatnia ramka BLE dopasowana do tagu."""

    adv: TagAdvertisement
    rssi: int
    source: str
    monotonic: float


def borrow_smartthings_token(hass: HomeAssistant) -> str | None:
    """Czyta aktualny access token wbudowanej integracji SmartThings.

    Tylko odczyt: nie odświeżamy go sami, bo refresh token SmartThings jest
    jednorazowy i zepsulibyśmy wbudowaną integrację.
    """
    for entry in hass.config_entries.async_entries("smartthings"):
        token = (entry.data.get("token") or {}).get("access_token")
        if token:
            return token
    return None


class SmartTagCoordinator(DataUpdateCoordinator[dict[str, TagInfo]]):
    """Trzyma metadane tagów z chmury i ostatnie obserwacje BLE."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=CLOUD_INTERVAL,
        )
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
        # privacy_id -> device_id; trzymane też w Store, żeby BLE działało bez chmury
        self.pid_index: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.sightings: dict[str, BleSighting] = {}

    def _token(self) -> str | None:
        if self.config_entry.data.get(CONF_TOKEN_SOURCE) == SOURCE_PAT:
            return self.config_entry.data.get(CONF_PAT)
        return borrow_smartthings_token(self.hass)

    async def async_load_cache(self) -> None:
        """Wczytuje pule privacy ID zapisane przy poprzednim starcie."""
        cached = await self._store.async_load() or {}
        self.names = cached.get("names", {})
        for device_id, pool in (cached.get("pools") or {}).items():
            for pid in pool:
                self.pid_index[pid] = device_id

    async def _async_update_data(self) -> dict[str, TagInfo]:
        token = self._token()
        if not token:
            if self.pid_index:
                _LOGGER.warning("Brak tokenu SmartThings, działam tylko na BLE z pamięci podręcznej")
                return self.data or {}
            raise ConfigEntryAuthFailed("Brak tokenu SmartThings")
        client = SmartThingsClient(async_get_clientsession(self.hass), token)
        try:
            devices = await client.async_list_tags()
        except SmartTagAuthError as err:
            if self.pid_index and self.config_entry.data.get(CONF_TOKEN_SOURCE) == SOURCE_PAT:
                _LOGGER.warning("PAT wygasł (PAT SmartThings żyje 24 h), BLE działa dalej z pamięci")
                return self.data or {}
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmartTagApiError as err:
            raise UpdateFailed(str(err)) from err

        infos: dict[str, TagInfo] = {}
        pools: dict[str, list[str]] = {}
        for dev in devices:
            info = parse_tag(dev)
            infos[info.device_id] = info
            self.names[info.device_id] = info.label
            pool = await self.hass.async_add_executor_job(pool_from_device, dev)
            if pool:
                pools[info.device_id] = sorted(pool)
        if pools:
            self.pid_index = {pid: dev_id for dev_id, pool in pools.items() for pid in pool}
            await self._store.async_save({"pools": pools, "names": self.names})
        return infos

    @callback
    def async_handle_bluetooth(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Dopasowuje ramkę FD5A do tagu po privacy ID."""
        raw = service_info.service_data.get(SMARTTAG_SERVICE_UUID)
        adv = parse_service_data(raw) if raw else None
        if adv is None:
            return
        device_id = self.pid_index.get(adv.privacy_id)
        if device_id is None:
            return
        self.sightings[device_id] = BleSighting(
            adv=adv,
            rssi=service_info.rssi,
            source=service_info.source,
            monotonic=time.monotonic(),
        )
        self.async_update_listeners()

    def known_device_ids(self) -> set[str]:
        """Tagi znane z chmury albo z pamięci podręcznej."""
        return set(self.data or {}) | set(self.pid_index.values())
