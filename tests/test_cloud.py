import cloud

DEVICE = {
    "deviceId": "abc",
    "name": "Tag(BLE)",
    "label": "Klucze",
    "presentationId": "IM-SmartTag-BLE",
    "ocfDeviceType": "x.com.st.d.tag",
    "components": [
        {
            "id": "main",
            "capabilities": [{"id": "tag.tagButton"}, {"id": "geolocation"}],
            "categories": [{"name": "BluetoothTracker"}],
        }
    ],
    "bleD2D": {
        "encryptionKey": "SECRET",
        "metadata": {
            "privacyIdPoolSize": 1000,
            "privacyIdSeed": "AAAA",
            "privacyIdInitialVector": "BBBB",
            "battery": {"level": "MEDIUM", "updated": 1624980489},
            "searchingStatus": "stop",
            "lastKnownConnection": {
                "updated": 1623044072000,
                "connectedDevice": {"name": "Galaxy S24"},
                "d2dStatus": "gattConnected",
                "nearby": True,
            },
            "onboardedBy": {"saGuid": "guid"},
            "vendor": {"modelName": "EI-T5600"},
        },
    },
}


def test_is_tag_variants():
    assert cloud.is_tag(DEVICE)
    assert cloud.is_tag({"components": [{"capabilities": [{"id": "tag.tagStatus"}]}]})
    assert cloud.is_tag({"components": [{"categories": [{"name": "BluetoothTracker"}]}]})
    assert not cloud.is_tag({"components": [{"capabilities": [{"id": "switch"}]}]})


def test_parse_tag():
    info = cloud.parse_tag(DEVICE)
    assert info.label == "Klucze"
    assert info.model == "EI-T5600"
    assert info.has_privacy_material
    assert info.battery == "MEDIUM"
    assert info.connected_device == "Galaxy S24"
    assert info.d2d_status == "gattConnected"
    assert info.nearby is True
    assert info.last_connection.year == 2021
    assert "SECRET" not in repr(info)


def test_parse_tag_without_ble():
    info = cloud.parse_tag({"deviceId": "x"})
    assert info.label == "x"
    assert not info.has_privacy_material
    assert info.battery is None


def test_find_fme():
    items = [
        {"installedAppId": "1", "ui": {"pluginId": "other"}},
        {"installedAppId": "2", "ui": {"pluginId": cloud.FME_PLUGIN_ID}},
    ]
    assert cloud.find_fme_installed_app(items) == "2"
    assert cloud.find_fme_installed_app([]) is None
