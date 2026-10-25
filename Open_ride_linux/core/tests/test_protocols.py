"""Tests des protocoles BLE (FTMS et Zwift Click), sans matériel."""

import struct

import pytest

from openride_core import ftms, zwift_click
from openride_core.zwift_click import (
    ClickButtons, InputEvent, PressClassifier, decode_protobuf_varints, parse_click_buttons,
)


def test_parse_indoor_bike_data_speed_cadence_power_hr():
    # Drapeaux : vitesse présente (bit 0 = 0), cadence (bit 2), puissance (bit 6), FC (bit 9).
    flags = 0x0004 | 0x0040 | 0x0200
    data = struct.pack("<HHHhB", flags, 3250, 170, 245, 151)
    d = ftms.parse_indoor_bike_data(data)
    assert d.speed_kmh == pytest.approx(32.5)
    assert d.cadence_rpm == pytest.approx(85.0)
    assert d.power_w == 245
    assert d.heart_rate_bpm == 151


def test_parse_indoor_bike_data_more_data_and_distance():
    # Bit 0 = 1 : pas de vitesse ; distance sur 24 bits (bit 4) puis puissance.
    flags = 0x0001 | 0x0010 | 0x0040
    data = struct.pack("<H", flags) + (70000).to_bytes(3, "little") + struct.pack("<h", 300)
    d = ftms.parse_indoor_bike_data(data)
    assert d.speed_kmh is None
    assert d.total_distance_m == 70000
    assert d.power_w == 300


def test_sim_params_encoding():
    raw = ftms.cmd_set_sim_params(-3.45, crr=0.004, cw_kg_m=0.20)
    op, wind, grade, crr, cw = struct.unpack("<BhhBB", raw)
    assert (op, wind, grade, crr, cw) == (0x11, 0, -345, 40, 20)


def test_target_power_encoding():
    assert ftms.cmd_set_target_power(212.6) == bytes([0x05]) + struct.pack("<h", 213)


def test_features_and_ranges():
    machine = (1 << 1) | (1 << 14)               # cadence, power
    target = (1 << 3) | (1 << 13)                # power target, indoor bike simulation
    f = ftms.parse_features(struct.pack("<II", machine, target))
    assert f.supports_erg and f.supports_sim
    assert "cadence" in f.machine
    pr = ftms.parse_power_range(struct.pack("<hhH", 0, 2000, 1))
    assert (pr.min_w, pr.max_w, pr.increment_w) == (0, 2000, 1)


def test_control_response():
    r = ftms.parse_control_response(bytes([0x80, 0x11, 0x01]))
    assert r.ok and r.request_op == 0x11
    r = ftms.parse_control_response(bytes([0x80, 0x05, 0x05]))
    assert not r.ok and r.result_name == "CONTROL_NOT_PERMITTED"
    assert ftms.parse_control_response(bytes([0x01])) is None


def test_hr_measurement():
    assert ftms.parse_hr_measurement(bytes([0x00, 72])) == 72
    assert ftms.parse_hr_measurement(bytes([0x01, 0x2C, 0x01])) == 300


def test_protobuf_varints():
    # champ 1 = 1, champ 2 = 0, champ 3 = 300
    assert decode_protobuf_varints(bytes([0x08, 0x01, 0x10, 0x00, 0x18, 0xAC, 0x02])) == {1: 1, 2: 0, 3: 300}


def test_click_buttons():
    minus_pressed = bytes([0x37, 0x08, 0x01, 0x10, 0x00])
    b = parse_click_buttons(minus_pressed)
    assert b.minus_pressed and not b.plus_pressed
    assert parse_click_buttons(bytes([0x19, 0x10, 0x5D])) is None  # batterie


def test_click_keypad_status_new_model():
    # Trames mesurées : 0xFFFFFFFF = rien ; bit 12 à 0 = +, bit 8 à 0 = −
    def frame(mask):
        out = bytearray([0x23, 0x08])
        v = mask
        while v > 0x7F:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        out.append(v)
        return bytes(out)

    none = parse_click_buttons(frame(0xFFFFFFFF))
    assert not none.plus_pressed and not none.minus_pressed
    plus = parse_click_buttons(frame(0xFFFFEFFF))
    assert plus.plus_pressed and not plus.minus_pressed
    minus = parse_click_buttons(frame(0xFFFFFEFF))
    assert minus.minus_pressed and not minus.plus_pressed
    both = parse_click_buttons(frame(0xFFFFEEFF))
    assert both.plus_pressed and both.minus_pressed
    # Click V2 : B du boîtier droit (bit 5, trame mesurée ffffffdf) = « − » ; Y (bit 6) = pause ;
    # A et Z ignorés
    b = parse_click_buttons(frame(0xFFFFFFDF))
    assert b.minus_pressed and not b.plus_pressed and not b.y_pressed
    y = parse_click_buttons(frame(0xFFFFFFBF))
    assert y.y_pressed and not y.minus_pressed and not y.plus_pressed
    for other in (0xFFFFFFEF, 0xFFFFFF7F):
        o = parse_click_buttons(frame(other))
        assert not o.minus_pressed and not o.plus_pressed and not o.y_pressed
    # Trames relevées sur le boîtier gauche : − fffffeff, flèches fffffffe/fd/fb/f7
    assert parse_click_buttons(frame(0xFFFFFEFF)).minus_pressed
    assert zwift_click.KEYPAD_BITS["MINUS"] == zwift_click.KEYPAD_MINUS_BIT
    assert zwift_click.KEYPAD_BITS["PLUS"] == zwift_click.KEYPAD_PLUS_BIT
    assert zwift_click.KEYPAD_BITS["B"] == zwift_click.KEYPAD_B_BIT
    for arrow in ("LEFT", "UP", "RIGHT", "DOWN"):
        o = parse_click_buttons(frame(0xFFFFFFFF & ~(1 << zwift_click.KEYPAD_BITS[arrow])))
        assert not o.minus_pressed and not o.plus_pressed
    # trame réelle du rapport : 2308ffffffff0f
    real = parse_click_buttons(bytes.fromhex("2308ffffffff0f"))
    assert not real.plus_pressed and not real.minus_pressed


def test_press_classifier_thresholds():
    c = PressClassifier()
    assert c.update("PLUS", True, 0.0) is None
    assert c.update("PLUS", True, 0.1) is None        # notification répétée
    assert c.update("PLUS", False, 0.3) == InputEvent.PLUS_SHORT
    c.update("MINUS", True, 1.0)
    assert c.update("MINUS", False, 2.3) == InputEvent.MINUS_LONG
    c.update("PLUS", True, 5.0)
    assert c.update("PLUS", False, 5.8) is None       # zone morte 500–1200 ms
    assert c.update("PLUS", False, 6.0) is None       # relâché sans appui


def test_y_button_is_pause_whatever_the_duration():
    """Lot N6 : bouton Y du boîtier droit = pause ou reprise, appui court ou long."""
    c = PressClassifier()
    assert c.feed(ClickButtons(False, False, y_pressed=True), 0.0) == []
    assert c.feed(ClickButtons(False, False), 0.2) == [InputEvent.PAUSE]
    c.feed(ClickButtons(False, False, y_pressed=True), 1.0)
    assert c.feed(ClickButtons(False, False), 2.0) == [InputEvent.PAUSE]   # zone morte ignorée
