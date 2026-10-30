"""Parser danych serwisowych BLE SmartTagów (UUID 0xFD5A).

Format według wiki uTag (KieronQuinn) i pracy Yu i in. (USENIX Security 2024).
Moduł nie importuje Home Assistant, więc da się go testować samodzielnie.
"""

from __future__ import annotations

from dataclasses import dataclass

SMARTTAG_SERVICE_UUID = "0000fd5a-0000-1000-8000-00805f9b34fb"
SERVICE_DATA_MIN_LEN = 20

TAG_STATES = {
    1: "premature_offline",  # < 15 min bez właściciela
    2: "offline",  # 15 min do 24 h bez właściciela
    3: "overmature_offline",  # > 24 h bez właściciela
    4: "connected_owner",  # połączony z 1 urządzeniem właściciela
    5: "connected_other",  # połączony z 1 urządzeniem nie-właściciela
    6: "connected_two",  # połączony z 2 urządzeniami
}

BATTERY_LEVELS = {0: "VERY_LOW", 1: "LOW", 2: "MEDIUM", 3: "FULL"}


@dataclass(frozen=True)
class TagAdvertisement:
    """Rozkodowana ramka FD5A."""

    version: int
    adv_type: int
    state: int
    state_name: str
    aging_counter: int
    privacy_id: str  # 8 bajtów hex, małe litery
    battery: str
    uwb: bool
    encrypted: bool
    region_id: int
    motion: bool
    activity_tracking: bool
    signature: str


def parse_service_data(data: bytes) -> TagAdvertisement | None:
    """Zwraca TagAdvertisement albo None, gdy ramka jest za krótka."""
    if data is None or len(data) < SERVICE_DATA_MIN_LEN:
        return None
    b0 = data[0]
    state = b0 & 0x07
    b12 = data[12]
    return TagAdvertisement(
        version=(b0 >> 4) & 0x0F,
        adv_type=(b0 >> 3) & 0x01,
        state=state,
        state_name=TAG_STATES.get(state, f"unknown_{state}"),
        aging_counter=int.from_bytes(data[1:4], "big"),
        privacy_id=data[4:12].hex(),
        battery=BATTERY_LEVELS[b12 & 0x03],
        uwb=bool((b12 >> 2) & 0x01),
        encrypted=bool((b12 >> 3) & 0x01),
        region_id=(b12 >> 4) & 0x0F,
        motion=bool((data[13] >> 7) & 0x01),
        activity_tracking=bool(data[15] & 0x01),
        signature=data[16:20].hex(),
    )
