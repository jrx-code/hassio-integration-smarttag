import ble

PID = bytes.fromhex("0102030405060708")


def frame(state=4, pid=PID, b12=0b0011_0111, b13=0x80, b15=0x01):
    return (
        bytes([(2 << 4) | (0 << 3) | state])
        + (1234).to_bytes(3, "big")
        + pid
        + bytes([b12, b13, 0x00, b15])
        + bytes.fromhex("deadbeef")
    )


def test_parse_full_frame():
    adv = ble.parse_service_data(frame())
    assert adv.version == 2
    assert adv.state == 4
    assert adv.state_name == "connected_owner"
    assert adv.aging_counter == 1234
    assert adv.privacy_id == "0102030405060708"
    assert adv.battery == "FULL"
    assert adv.uwb is True
    assert adv.encrypted is False
    assert adv.region_id == 3
    assert adv.motion is True
    assert adv.activity_tracking is True
    assert adv.signature == "deadbeef"


def test_short_frame_is_ignored():
    assert ble.parse_service_data(b"\x01\x02") is None
    assert ble.parse_service_data(None) is None


def test_unknown_state():
    assert ble.parse_service_data(frame(state=7)).state_name == "unknown_7"
