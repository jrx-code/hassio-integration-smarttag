"""Pomocnicze funkcje do oficjalnego API SmartThings (bez zależności od HA).

Działa z tokenem PAT albo tokenem OAuth SmartThings. Zwraca tylko to, co API
naprawdę udostępnia: metadane BLE tagów, baterię, ostatnie połączenie.
Lokalizacji (geolocation) API dla tagów nie wypełnia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

API_BASE = "https://api.smartthings.com/v1"
TAG_OCF_TYPE = "x.com.st.d.tag"
FME_PLUGIN_ID = "com.samsung.android.plugin.fme"


def is_tag(device: dict) -> bool:
    """Rozpoznaje SmartTag w liście urządzeń."""
    if device.get("ocfDeviceType") == TAG_OCF_TYPE:
        return True
    if device.get("bleD2D") or device.get("type") == "BLE_D2D":
        return True
    for comp in device.get("components") or []:
        for cap in comp.get("capabilities") or []:
            if str(cap.get("id", "")).startswith("tag."):
                return True
        for cat in comp.get("categories") or []:
            if cat.get("name") == "BluetoothTracker":
                return True
    return False


def _ts(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    if value > 10**11:  # milisekundy
        value //= 1000
    return datetime.fromtimestamp(value, tz=UTC)


@dataclass
class TagInfo:
    """To, co da się wyczytać z opisu urządzenia."""

    device_id: str
    label: str
    model: str | None = None
    capabilities: list[str] = field(default_factory=list)
    has_ble_d2d: bool = False
    has_privacy_material: bool = False
    battery: str | None = None
    battery_updated: datetime | None = None
    searching_status: str | None = None
    connected_device: str | None = None
    d2d_status: str | None = None
    nearby: bool | None = None
    last_connection: datetime | None = None
    onboarded_by: str | None = None


def parse_tag(device: dict) -> TagInfo:
    """Wyciąga TagInfo z odpowiedzi GET /devices/{id}. Nie kopiuje sekretów."""
    ble = device.get("bleD2D") or {}
    meta = ble.get("metadata") or {}
    battery = meta.get("battery") or {}
    conn = meta.get("lastKnownConnection") or {}
    vendor = meta.get("vendor") or {}
    caps = [
        cap.get("id")
        for comp in device.get("components") or []
        for cap in comp.get("capabilities") or []
        if cap.get("id")
    ]
    return TagInfo(
        device_id=device.get("deviceId", ""),
        label=device.get("label") or device.get("name") or device.get("deviceId", ""),
        model=vendor.get("modelName") or device.get("presentationId") or device.get("name"),
        capabilities=caps,
        has_ble_d2d=bool(ble),
        has_privacy_material=bool(
            ble.get("encryptionKey")
            and meta.get("privacyIdSeed")
            and meta.get("privacyIdInitialVector")
            and meta.get("privacyIdPoolSize")
        ),
        battery=battery.get("level"),
        battery_updated=_ts(battery.get("updated")),
        searching_status=meta.get("searchingStatus"),
        connected_device=(conn.get("connectedDevice") or {}).get("name"),
        d2d_status=conn.get("d2dStatus"),
        nearby=conn.get("nearby"),
        last_connection=_ts(conn.get("updated")),
        onboarded_by=(meta.get("onboardedBy") or {}).get("saGuid"),
    )


def find_fme_installed_app(items: list[dict]) -> str | None:
    """Szuka installedAppId wtyczki SmartThings Find (FME)."""
    for item in items:
        if (item.get("ui") or {}).get("pluginId") == FME_PLUGIN_ID:
            return item.get("installedAppId")
    return None
