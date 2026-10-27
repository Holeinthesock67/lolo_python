"""Recette guidée du Zwift Click (lot X8) : relevé par boîtier, silences, étapes guidées sur le Click simulé."""

import asyncio
import json

import pytest

from openride_core import ble_sim, sim_scenarios, zwift_click
from openride_core.config import Config
from openride_core.tools import click_recette as cr
from openride_core.zwift_click import InputEvent


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_recorder_buttons_side_battery_and_other_types():
    clock = Clock()
    rec = cr.Recorder(clock)
    rec.raw("AA", ble_sim.keypad_message(False, True))                       # − du boîtier gauche
    rec.raw("BB", ble_sim.keypad_message(False, False, [zwift_click.KEYPAD_BITS["B"]]))
    rec.raw("BB", ble_sim.battery_message(64))
    rec.raw("BB", bytes([zwift_click.MSG_EMPTY]))
    rec.raw("CC", ble_sim.keypad_message(True, False))
    assert rec.unit("AA").side == "gauche" and rec.unit("AA").buttons == {"MINUS": 1}
    assert rec.unit("BB").side == "droit" and rec.unit("BB").battery_pct == 64
    assert rec.unit("BB").other_types == {"0x15": 1}
    assert rec.unit("CC").side == "?"   # « + » seul : relayé aussi par le boîtier gauche
    assert rec.unit("AA").notifications == 1 and rec.unit("BB").notifications == 3


def test_recorder_silence_only_while_connected():
    clock = Clock()
    rec = cr.Recorder(clock)
    rec.link("AA", True)
    rec.raw("AA", ble_sim.keypad_message(False, False))
    clock.now += 1.0
    rec.check_silence({"AA": True})
    assert rec.unit("AA").silences == []
    clock.now += 4.0
    rec.check_silence({"AA": True})
    clock.now += 3.0
    rec.raw("AA", ble_sim.keypad_message(False, False))   # le boîtier reparle : silence de 8 s
    assert rec.unit("AA").silences == [(0.0, 8.0)]
    clock.now += 10.0
    rec.link("AA", False)
    rec.check_silence({"AA": False})                      # coupé : une coupure, pas un silence
    rec.close()
    assert rec.unit("AA").silences == [(0.0, 8.0)] and len(rec.unit("AA").drops) == 1


def run_sim(spec: dict, minutes: float, reminder: float) -> tuple[cr.Recorder, dict]:
    async def go():
        world = sim_scenarios.build_world(spec, trainer=False, hr=False)
        prompts: asyncio.Queue[str] = asyncio.Queue()
        rec = cr.Recorder(asyncio.get_running_loop().time)
        providers = cr.make_providers(rec, Config(), world)
        extra = [asyncio.create_task(world.run()), asyncio.create_task(cr.sim_user(world, prompts))]
        try:
            report = await cr.run_recette(providers, rec, minutes, reminder, prompts.put_nowait,
                                          step_timeout=5.0, connect_timeout=10.0, tick_s=0.1)
        finally:
            world.stop()
            for t in extra:
                t.cancel()
            await asyncio.gather(*extra, return_exceptions=True)
        return rec, report
    return asyncio.run(go())


@pytest.mark.slow   # une vingtaine de secondes
def test_guided_steps_on_simulated_click(tmp_path):
    rec, report = run_sim({"click": {"appear_at": 0.0}, "events": []}, minutes=0.12, reminder=0.05)
    assert report["guided_ok"] == report["guided_total"] == len(cr.STEPS), report["steps"]
    sides = {s["key"]: s["side"] for s in report["steps"]}
    assert sides["plus"] == sides["b"] == sides["y"] == "droit" and sides["minus"] == "gauche"
    assert any(s["key"].startswith("rappel") and s["ok"] for s in report["steps"])
    assert report["ok"] and len(report["units"]) == 2
    assert all(u["battery_pct"] == 80 and 8 < u["rate_per_s"] < 12 for u in report["units"])
    cr.write_outputs(rec, report, tmp_path)
    assert "tout passe" in (tmp_path / "rapport.txt").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "rapport.json").read_text(encoding="utf-8"))["ok"] is True
    assert (tmp_path / "notifications.csv").read_text(encoding="utf-8").startswith("t_s;")


@pytest.mark.slow
def test_silent_left_unit_and_missing_step_are_reported():
    spec = {"click": {"appear_at": 0.0}, "events": [
        {"t": 3.0, "device": "click_minus", "action": "silence", "seconds": 600}]}
    _rec, report = run_sim(spec, minutes=0.02, reminder=1.0)
    left = next(u for u in report["units"] if u["address"] == sim_scenarios.MINUS_ADDRESS)
    assert left["silences"] and left["silences"][0]["duration_s"] > 5.0
    steps = {s["key"]: s for s in report["steps"]}
    assert steps["minus"]["ok"] is False and "non reçu" in steps["minus"]["detail"]
    assert steps["plus"]["ok"] is True
    assert report["ok"] is False
    assert "SILENCES" in cr.report_text(report)
    assert InputEvent.MINUS_SHORT.value not in left["events"]
