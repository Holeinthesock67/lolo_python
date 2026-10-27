"""Zwift Click avant et après une mise à jour du firmware : relevé BLE, trames, comparaison et verdict."""

import asyncio
import copy
import json
import time

import pytest

from openride_core import ble_sim, sim_scenarios, zwift_click
from openride_core.config import Config
from openride_core.tools import click_firmware as cf
from openride_core.tools import click_recette as cr

DIS_SVC = "0000180a-0000-1000-8000-00805f9b34fb"


class Char:
    def __init__(self, uuid, props):
        self.uuid, self.properties = uuid, props


class Svc:
    def __init__(self, uuid, chars):
        self.uuid, self.characteristics = uuid, chars


class FakeClick:
    """Boîtier factice : Device Information, batterie, service Zwift qui répond au RideOn."""

    def __init__(self, firmware="1.1.0", extra_char=False):
        zw = [Char(zwift_click.ZWIFT_ASYNC, ["notify"]), Char(zwift_click.ZWIFT_SYNC_RX, ["write"]),
              Char(zwift_click.ZWIFT_SYNC_TX, ["indicate"])]
        if extra_char:
            zw.append(Char(zwift_click.ZWIFT_UNKNOWN_6, ["read", "notify"]))
        self.services = [Svc(DIS_SVC, [Char(u, ["read"]) for u in cf.DIS.values()]),
                         Svc("0000180f-0000-1000-8000-00805f9b34fb", [Char(cf.BATTERY_LEVEL, ["read"])]),
                         Svc(zwift_click.ZWIFT_SERVICE, zw)]
        self.values = {cf.DIS["fabricant"]: b"Zwift", cf.DIS["modele"]: b"Click V2", cf.DIS["firmware"]: firmware.encode(),
                       cf.DIS["materiel"]: b"B", cf.DIS["logiciel"]: b"1.0\x00", cf.BATTERY_LEVEL: bytes([77])}
        self.notify = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read_gatt_char(self, uuid):
        return bytearray(self.values[uuid])

    async def start_notify(self, uuid, cb):
        self.notify[uuid] = cb

    async def write_gatt_char(self, uuid, data, response=True):
        assert data == zwift_click.RIDE_ON
        self.notify[zwift_click.ZWIFT_SYNC_TX](None, bytearray(b"RideOn\x01\x02"))
        for _ in range(3):
            self.notify[zwift_click.ZWIFT_ASYNC](None, bytearray(ble_sim.keypad_message(False, False)))
        self.notify[zwift_click.ZWIFT_ASYNC](None, bytearray(ble_sim.battery_message(77)))


def test_releve_reads_versions_gatt_and_rideon():
    ads = [{"address": "AA", "name": "Zwift Click", "rssi": -50, "service_uuids": [], "manufacturer_data": {}},
           {"address": "ZZ", "name": "Autre", "rssi": -60, "service_uuids": [], "manufacturer_data": {}}]

    async def scan(_t):
        return ads

    profile = asyncio.run(cf.releve(scan, lambda _a: FakeClick(), scan_s=0, listen_s=0, say=lambda _s: None))
    assert len(profile["units"]) == 1          # l'appareil qui n'est pas un Click est ignoré
    u = profile["units"][0]
    assert u["dis"] == {"fabricant": "Zwift", "modele": "Click V2", "firmware": "1.1.0", "materiel": "B", "logiciel": "1.0"}
    assert u["battery_pct"] == 77 and u["error"] is None
    assert u["rideon_reply_hex"] == b"RideOn\x01\x02".hex()
    assert u["first_types"] == {"0x23": 3, "0x19": 1}
    assert [s["uuid"] for s in u["gatt"]] == sorted(s["uuid"] for s in u["gatt"])
    assert "firmware 1.1.0" in cf.profile_text(profile)


def test_releve_notes_connection_error():
    class Broken:
        async def __aenter__(self):
            raise TimeoutError("pas de réponse")

        async def __aexit__(self, *exc):
            return False

    u = asyncio.run(cf.profile_unit({"address": "AA", "name": "Zwift Click"}, lambda _a: Broken(), 0))
    assert u["error"].startswith("TimeoutError") and u["gatt"] == []


def test_frame_stats_intervals_lengths_and_repeats():
    k = ble_sim.keypad_message(False, False)
    frames = [(0.0, k), (0.1, k), (0.2, ble_sim.keypad_message(True, False)), (0.5, k)]
    s = cf.frame_stats(frames)
    assert s["frames"] == 4 and s["interval_ms_p50"] == 100.0 and s["interval_ms_max"] == 300.0
    assert s["types"] == {"0x23": 4} and s["repeat_ratio"] == 0.25


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_tracing_recorder_writes_frames(tmp_path):
    clock = Clock()
    rec = cf.TracingRecorder(clock)
    for i in range(5):
        clock.now = i * 0.1
        rec.raw("AA", ble_sim.keypad_message(False, i == 2))
    rec.write_extra(tmp_path)
    lines = (tmp_path / "trames.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "t_s;boitier;type;longueur;octets" and len(lines) == 6
    stats = json.loads((tmp_path / "trames_stats.json").read_text(encoding="utf-8"))
    assert stats["AA"]["side"] == "gauche" and stats["AA"]["frames"] == 5


# --- Comparaison sur des captures écrites à la main ------------------------------------------------

def unit_profile(address, firmware, extra_char=False):
    c = FakeClick(firmware, extra_char)
    return {"address": address, "name": "Zwift Click", "dis": {"firmware": firmware, "modele": "Click V2"},
            "battery_pct": 80, "rideon_reply_hex": b"RideOn\x01\x02".hex(), "error": None,
            "gatt": [{"uuid": s.uuid, "characteristics": [{"uuid": ch.uuid, "properties": ch.properties}
                                                          for ch in s.characteristics]} for s in c.services]}


def recette_unit(address, side, silences=0, drops=0, buttons=None):
    return {"address": address, "side": side, "battery_pct": 80, "drops": drops,
            "silences": [{"start_s": 60.0 * i, "duration_s": 30.0} for i in range(silences)],
            "max_silence_s": 30.0 if silences else 0.0,
            "buttons": buttons or ({"MINUS": 20} if side == "gauche" else {"PLUS": 20, "B": 4, "Y": 2})}


def steps(delay=0.8, ok=True):
    return [{"key": k, "ok": ok, "delay_s": delay, "side": side}
            for k, side in (("plus", "droit"), ("minus", "gauche"), ("b", "droit"), ("y", "droit"),
                            ("plus_long", "droit"), ("minus_long", "gauche"))]


def stats(side, types=None, p50=100.0):
    return {"side": side, "frames": 18000, "interval_ms_p50": p50, "interval_ms_p95": 120.0,
            "interval_ms_max": 300.0, "types": types or {"0x23": 17990, "0x19": 10},
            "lengths": {"0x23": [6, 7], "0x19": [3]}, "repeat_ratio": 0.98}


def write_capture(folder, firmware="1.1.0", left_silences=3, guided=6, extra_char=False, types=None):
    (folder / "recette").mkdir(parents=True)
    profile = {"date": "x", "units": [unit_profile("L1", firmware, extra_char), unit_profile("R1", firmware)]}
    st = steps()
    for s in st[guided:]:
        s.update(ok=False, delay_s=None, side=None)
    report = {"ok": False, "minutes": 30, "steps": st, "guided_ok": guided, "guided_total": 6,
              "units": [recette_unit("L1", "gauche", left_silences), recette_unit("R1", "droit")]}
    (folder / "profil_ble.json").write_text(json.dumps(profile), encoding="utf-8")
    (folder / "recette" / "rapport.json").write_text(json.dumps(report), encoding="utf-8")
    (folder / "recette" / "trames_stats.json").write_text(
        json.dumps({"L1": stats("gauche", types), "R1": stats("droit")}), encoding="utf-8")
    return folder


def test_same_capture_is_same_and_warns_firmware_unchanged(tmp_path):
    a = cf.load_capture(write_capture(tmp_path / "a"))
    c = cf.compare(a, copy.deepcopy(a))
    assert c["verdict"] == "PAREIL" and not c["protocol_changed"]
    assert any("identique" in n for n in c["notes"])


def test_fewer_left_silences_is_better_with_unlock_caveat(tmp_path):
    before = cf.load_capture(write_capture(tmp_path / "a", "1.1.0", left_silences=4))
    after = cf.load_capture(write_capture(tmp_path / "b", "1.3.0", left_silences=0))
    c = cf.compare(before, after)
    assert c["verdict"] == "MIEUX" and not c["protocol_changed"]
    left = next(r for r in c["units"] if r["side"] == "gauche")
    assert left["firmware"] == ["1.1.0", "1.3.0"] and left["silences"] == [4, 0]
    assert any("24 h" in n for n in c["notes"])
    text = cf.compare_text(c)
    assert "MIEUX" in text and "1.1.0 → 1.3.0" in text and "L1" not in text   # pas d'adresse affichée


def test_protocol_change_is_flagged(tmp_path):
    before = cf.load_capture(write_capture(tmp_path / "a"))
    after = cf.load_capture(write_capture(tmp_path / "b", "1.3.0", extra_char=True,
                                          types={"0x23": 17000, "0x19": 10, "0x2A": 990}))
    c = cf.compare(before, after)
    assert c["protocol_changed"]
    assert any("table GATT" in p for p in c["protocol"]) and any("0x2A" in p for p in c["protocol"])
    assert "PROTOCOLE BLE MODIFIÉ" in cf.compare_text(c)


def test_lost_buttons_is_worse_and_cli_exit_code(tmp_path):
    write_capture(tmp_path / "click_2026-10-27_0400_avant_maj")
    write_capture(tmp_path / "click_2026-10-27_0600_apres_maj", "1.3.0", guided=4)
    assert cf.main(["compare", "--logs", str(tmp_path)]) == 1
    out = json.loads((tmp_path / "click_2026-10-27_0600_apres_maj" / "comparaison.json").read_text(encoding="utf-8"))
    assert out["verdict"] == "MOINS BIEN" and out["guided_ok"] == [6, 4]


@pytest.mark.slow   # une vingtaine de secondes
def test_capture_on_simulated_click_then_compare(tmp_path):
    async def go(rec):
        world = sim_scenarios.build_world({"click": {"appear_at": 0.0}, "events": []}, trainer=False, hr=False)
        prompts: asyncio.Queue[str] = asyncio.Queue()
        providers = cr.make_providers(rec, Config(), world)
        extra = [asyncio.create_task(world.run()), asyncio.create_task(cr.sim_user(world, prompts))]
        try:
            return await cr.run_recette(providers, rec, 0.05, 1.0, prompts.put_nowait,
                                        step_timeout=5.0, connect_timeout=10.0, tick_s=0.1)
        finally:
            world.stop()
            for t in extra:
                t.cancel()
            await asyncio.gather(*extra, return_exceptions=True)

    folders = []
    for name in ("click_a_avant_maj", "click_b_apres_maj"):
        rec = cf.TracingRecorder(time.monotonic)
        report = asyncio.run(go(rec))
        out = tmp_path / name
        cr.write_outputs(rec, report, out / "recette")
        cf.write_profile({"date": "x", "units": []}, out)
        folders.append(out)
    stats_ = json.loads((folders[0] / "recette" / "trames_stats.json").read_text(encoding="utf-8"))
    assert {s["side"] for s in stats_.values()} == {"gauche", "droit"}
    assert all(80 < s["interval_ms_p50"] < 120 for s in stats_.values())
    c = cf.compare(cf.load_capture(folders[0]), cf.load_capture(folders[1]))
    assert c["verdict"] in ("PAREIL", "MIEUX", "MOINS BIEN") and not c["protocol_changed"], c
