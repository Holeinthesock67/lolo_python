"""Ceinture cardio réelle (lot M2) : décodage complet de 0x2A37, contact, choix de l'appareil,
batterie. Les appareils sont ceux du Bluetooth simulé (`ble_sim.py`), comme dans la séance."""

from __future__ import annotations

import asyncio
import itertools
import logging
import struct

import pytest

from openride_core import ftms, hr_monitor
from openride_core.ble_sim import WATCH_ADDRESS
from openride_core.hr_monitor import HeartRateProvider, HrCandidate, choose_device, looks_like_watch
from openride_core.sim_scenarios import SimScenarioError, build_world, validate

STRAP = {"appear_at": 0.0, "connect_delay_s": 0.05, "tau_s": 1.0}


async def wait_for(cond, timeout=5.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        assert asyncio.get_running_loop().time() < end, "délai dépassé"
        await asyncio.sleep(0.02)


# --- décodage -------------------------------------------------------------------------------

def _frame(bpm: int, wide: bool, contact: str, energy: int | None, rr: list[int]) -> bytes:
    """Trame écrite à la main d'après Heart Rate Service 1.0 (sans passer par le décodeur)."""
    flags = 0x01 if wide else 0x00
    flags |= {"none": 0x00, "absent": 0x04, "present": 0x06}[contact]
    if energy is not None:
        flags |= 0x08
    if rr:
        flags |= 0x10
    out = bytes([flags]) + (struct.pack("<H", bpm) if wide else bytes([bpm]))
    if energy is not None:
        out += struct.pack("<H", energy)
    for v in rr:
        out += struct.pack("<H", v)
    return out


@pytest.mark.parametrize("wide, contact, energy, n_rr", list(itertools.product(
    (False, True), ("none", "absent", "present"), (None, 1234), (0, 1, 2, 9))))
def test_parse_full_every_flag_combination(wide, contact, energy, n_rr):
    bpm = 301 if wide else 72
    rr = [1024 - 10 * i for i in range(n_rr)]
    m = ftms.parse_hr_measurement_full(_frame(bpm, wide, contact, energy, rr))
    assert m.bpm == bpm
    assert m.contact == {"none": None, "absent": False, "present": True}[contact]
    assert m.energy_kj == energy
    assert m.rr_ms == pytest.approx([v * 1000 / 1024 for v in rr])
    assert ftms.parse_hr_measurement(_frame(bpm, wide, contact, energy, rr)) == bpm


def test_parse_full_known_vectors_and_errors():
    m = ftms.parse_hr_measurement_full(bytes([0x16, 60, 0x00, 0x04]))   # 60 bpm, RR 1024/1024 s
    assert (m.bpm, m.contact, m.rr_ms) == (60, True, [1000.0])
    for short in (b"", b"\x00", b"\x01\x2c", b"\x08\x48\x01"):
        with pytest.raises(ValueError):
            ftms.parse_hr_measurement_full(short)


def test_simulated_strap_frames_are_consistent():
    world = build_world({"hr": {**STRAP, "bpm": 120}})
    m = ftms.parse_hr_measurement_full(world.hr.measurement())
    assert m.bpm == 120 and m.contact is True
    assert m.rr_ms[0] == pytest.approx(500, abs=1)   # 60 000 / 120


# --- contact ------------------------------------------------------------------------------

def test_contact_lost_then_back(monkeypatch, caplog):
    monkeypatch.setattr(hr_monitor, "STALE_S", 1.5)

    async def scenario():
        world = build_world({"hr": {**STRAP, "bpm": 140}}, trainer=False, click=False)
        hr = HeartRateProvider(None, "", device_finder=world.find_device,
                               client_factory=world.client_factory)
        tasks = [asyncio.create_task(p.run()) for p in (hr, world)]
        await wait_for(lambda: hr.bpm == 140, timeout=4)
        await world.apply({"t": 0, "device": "hr", "action": "contact", "value": False})
        t0 = world.now()
        await wait_for(lambda: hr.bpm is None, timeout=4)
        assert world.now() - t0 <= hr_monitor.STALE_S + 1.1   # dernière bonne mesure ≤ 1 s avant
        await asyncio.sleep(3.0)   # contact absent pendant plusieurs mesures
        assert hr.bpm is None and hr.contact is False
        await world.apply({"t": 0, "device": "hr", "action": "contact", "value": True})
        await wait_for(lambda: hr.bpm == 140, timeout=3)
        assert len(hr.last_rr_ms) >= 2 and all(abs(v - 60000 / 140) < 2 for v in hr.last_rr_ms)
        for p in (hr, world):
            p.stop()
        await asyncio.wait(tasks, timeout=3)
    with caplog.at_level(logging.INFO, logger="hr"):
        asyncio.run(scenario())
    lines = [r.getMessage() for r in caplog.records if r.name == "hr" and "contact" in r.getMessage()]
    assert len(lines) == 2, lines
    assert "absent" in lines[0] and "retrouvé" in lines[1]


def test_strap_removed_without_contact_support():
    """Ceinture retirée sans gestion du contact (SRS §4.1) : 0 bpm ou fin des mesures -> None."""
    now = [100.0]
    hr = HeartRateProvider(None, "", device_finder=lambda *a, **k: None, clock=lambda: now[0])
    hr._on_hr(None, bytearray(_frame(105, False, "none", None, [])))
    assert hr.bpm == 105 and hr.contact is None
    hr._on_hr(None, bytearray(_frame(0, False, "none", None, [])))   # 0 = pas de mesure
    assert hr.bpm is None
    hr._on_hr(None, bytearray(_frame(105, False, "none", None, [])))
    now[0] += hr_monitor.STALE_S + 0.1   # plus aucune notification
    assert hr.bpm is None


def test_rr_history_is_bounded():
    hr = HeartRateProvider(None, "", device_finder=lambda *a, **k: None)
    for _ in range(50):
        hr._on_hr(None, bytearray(_frame(60, False, "present", None, [1024])))
    assert len(hr.last_rr_ms) == hr_monitor.RR_KEEP


# --- choix de l'appareil ------------------------------------------------------------------

def test_watch_names():
    assert looks_like_watch("Forerunner 265") and looks_like_watch("fenix 7") \
        and looks_like_watch("Venu 3") and looks_like_watch("Apple Watch")
    assert not looks_like_watch("HRM-Pro:123") and not looks_like_watch("Polar H10 1234")


def test_choose_device_rules():
    strap = HrCandidate("HRM-Dual:1", "AA", -80)
    watch = HrCandidate("Forerunner 265", "BB", -40)
    other = HrCandidate("TICKR X", "CC", -70)
    assert choose_device([watch, strap], "") is strap   # montre écartée malgré son RSSI
    assert choose_device([watch, strap, other], "") is other   # meilleur RSSI hors montres
    assert choose_device([watch], "") is watch
    assert choose_device([watch, strap], "forerunner") is watch
    assert choose_device([strap], "polar") is None
    assert choose_device([], "") is None


def _run_pick(spec, **kw):
    async def scenario():
        world = build_world(spec, trainer=False, click=False)
        contacted = []
        factory = world.client_factory

        def spy(device, **k):
            contacted.append(str(getattr(device, "address", device)).upper())
            return factory(device, **k)
        hr = HeartRateProvider(kw.get("address"), kw.get("name", ""),
                               device_finder=world.find_device, client_factory=spy)
        tasks = [asyncio.create_task(p.run()) for p in (hr, world)]
        await wait_for(lambda: hr.connected, timeout=6)
        for p in (hr, world):
            p.stop()
        await asyncio.wait(tasks, timeout=3)
        return hr, contacted
    return asyncio.run(scenario())


def test_strap_preferred_over_a_stronger_watch(caplog):
    with caplog.at_level(logging.INFO, logger="hr"):
        hr, contacted = _run_pick({"hr": {**STRAP, "rssi": -85}, "hr_watch": {**STRAP, "rssi": -40}})
    assert contacted == ["C0:FF:EE:00:18:0D"] and hr.device_address == "C0:FF:EE:00:18:0D"
    msgs = [r.getMessage() for r in caplog.records]
    found = next(m for m in msgs if m.startswith("Appareils cardio trouvés"))
    assert "HRM (sim)" in found and "Forerunner 265 (sim)" in found and "montre" in found
    assert any('hr_address = "C0:FF:EE:00:18:0D"' in m for m in msgs)


def test_watch_alone_is_chosen():
    hr, contacted = _run_pick({"hr_watch": STRAP})
    assert contacted == [WATCH_ADDRESS]


def test_given_address_is_the_only_device_contacted():
    hr, contacted = _run_pick({"hr": STRAP, "hr_watch": STRAP}, address=WATCH_ADDRESS)
    assert set(contacted) == {WATCH_ADDRESS}


def test_hr_name_picks_the_named_device():
    hr, contacted = _run_pick({"hr": STRAP, "hr_watch": STRAP}, name="forerunner")
    assert contacted == [WATCH_ADDRESS]


# --- batterie -----------------------------------------------------------------------------

def test_low_battery_warning(caplog):
    with caplog.at_level(logging.INFO, logger="hr"):
        hr, _ = _run_pick({"hr": {**STRAP, "battery_pct": 10}})
    assert hr.battery_pct == 10
    assert any(r.levelname == "WARNING" and "batterie faible (10 %)" in r.getMessage()
               for r in caplog.records)


def test_battery_absent_or_normal():
    hr, _ = _run_pick({"hr": {**STRAP, "battery_pct": None}})
    assert hr.battery_pct is None
    hr, _ = _run_pick({"hr": {**STRAP, "battery_pct": 75}})
    assert hr.battery_pct == 75


# --- scénarios ----------------------------------------------------------------------------

@pytest.mark.parametrize("spec, message", [
    ({"hr": {"contact": "oui"}}, "contact"),
    ({"hr": {"battery_pct": 140}}, "battery_pct"),
    ({"hr_watch": {"inconnu": 1}}, "inconnu"),
    ({"events": [{"t": 1, "device": "hr", "action": "contact", "value": 3}]}, "contact"),
])
def test_new_scenario_keys_are_validated(spec, message):
    with pytest.raises(SimScenarioError, match=message):
        validate(spec)


def test_new_scenario_keys_are_accepted():
    world = build_world({"hr": {"contact": None, "battery_pct": 50, "rssi": -70},
                         "hr_watch": {"rssi": -30},
                         "events": [{"t": 1, "device": "hr_watch", "action": "contact",
                                     "value": False}]})
    assert world.hr.contact is None and world.hr.battery_pct == 50
    assert world.hr_watch.address == WATCH_ADDRESS and world.hr_watch.rssi == -30
    assert len(world.events) == 1
    assert ftms.parse_hr_measurement_full(world.hr.measurement()).contact is None
