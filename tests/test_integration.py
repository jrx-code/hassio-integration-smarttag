"""Testy integracji HA (wymagają pytest-homeassistant-custom-component)."""

import base64
import time
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.smarttag.const import (  # noqa: E402
    CONF_PAT,
    CONF_TOKEN_SOURCE,
    DOMAIN,
    SOURCE_PAT,
)
from custom_components.smarttag.privacy import generate_pool  # noqa: E402

KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()
SEED = base64.b64encode(bytes(range(100, 112))).decode()
IV = base64.b64encode(bytes(16)).decode()

TAG = {
    "deviceId": "tag-1",
    "label": "Klucze",
    "ocfDeviceType": "x.com.st.d.tag",
    "components": [{"id": "main", "capabilities": [{"id": "tag.tagButton"}]}],
    "bleD2D": {
        "encryptionKey": KEY,
        "metadata": {
            "privacyIdPoolSize": 20,
            "privacyIdSeed": SEED,
            "privacyIdInitialVector": IV,
            "battery": {"level": "MEDIUM", "updated": 1700000000},
            "lastKnownConnection": {"connectedDevice": {"name": "Galaxy S24"}, "nearby": True},
        },
    },
}
CLIENT = "custom_components.smarttag.api.SmartThingsClient.async_list_tags"


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations, hass):
    hass.config.components.add("bluetooth_adapters")
    hass.config.components.add("bluetooth")
    yield


async def test_config_flow_pat(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(CLIENT, return_value=[TAG]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN_SOURCE: SOURCE_PAT, CONF_PAT: "x"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_TOKEN_SOURCE: SOURCE_PAT, CONF_PAT: "x"}


async def test_config_flow_no_tags(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(CLIENT, return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN_SOURCE: SOURCE_PAT, CONF_PAT: "x"}
        )
    assert result["errors"] == {"base": "no_tags"}


class FakeServiceInfo:
    def __init__(self, data: bytes, rssi: int = -60, source: str = "proxy-salon"):
        self.service_data = {"0000fd5a-0000-1000-8000-00805f9b34fb": data}
        self.rssi = rssi
        self.source = source


async def test_setup_and_ble_match(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN_SOURCE: SOURCE_PAT, CONF_PAT: "x"})
    entry.add_to_hass(hass)
    with (
        patch(CLIENT, return_value=[TAG]),
        patch("homeassistant.components.bluetooth.async_register_callback", return_value=lambda: None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    states = {s.entity_id: s.state for s in hass.states.async_all()}
    assert any(e.startswith("binary_sensor.klucze") for e in states), states
    presence = next(e for e in states if e.startswith("binary_sensor.klucze"))
    battery = next(e for e in states if e.startswith("sensor.klucze") and "bat" in e)
    assert states[presence] == "off"
    assert states[battery] == "50"

    pid = bytes.fromhex(sorted(generate_pool(KEY, 20, SEED, IV))[3])
    frame = bytes([0x24]) + (7).to_bytes(3, "big") + pid + bytes([0x07, 0x00, 0x00, 0x00]) + bytes(4)
    coordinator.async_handle_bluetooth(FakeServiceInfo(frame), None)
    await hass.async_block_till_done()
    assert hass.states.get(presence).state == "on"
    assert hass.states.get(presence).attributes["source"] == "proxy-salon"
    assert hass.states.get(battery).state == "100"

    # Obca ramka (pid spoza puli) niczego nie zmienia
    other = bytes([0x22]) + bytes(3) + bytes(8) + bytes(8)
    coordinator.async_handle_bluetooth(FakeServiceInfo(other, rssi=-90), None)
    assert coordinator.sightings["tag-1"].rssi == -60

    # Po czasie bez ramek: nieobecny
    coordinator.sightings["tag-1"].monotonic = time.monotonic() - 10_000
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(presence).state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)
