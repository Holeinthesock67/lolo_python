"""Journal de séance, lot M4 : biais ERG (`erg_bias_pct`) et lignes `device` des coupures."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.fit_export import iter_records, journal_to_fit
from openride_core.input_providers import NullProvider
from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.tools.session_summary import compute_summary, load_session
from openride_core.zwift_click import InputEvent

TWO_BLOCKS_ZWO = """<workout_file><name>Deux blocs</name><workout>
<SteadyState Duration="60" Power="0.6"/>
<SteadyState Duration="120" Power="0.8"/>
</workout></workout_file>
"""


def _session(tmp_path, monkeypatch, port):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wdir = tmp_path / "workouts"
    wdir.mkdir()
    (wdir / "deux_blocs.zwo").write_text(TWO_BLOCKS_ZWO, encoding="utf-8")
    cfg = Config()
    cfg.rider.ftp_w = 250.0
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    driver = MockDriver()
    s = CoreSession(cfg, driver=driver, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=wdir)
    s.server.send_error = lambda code, message: None   # type: ignore[method-assign]
    return s, driver


def run(s, seconds, dt=0.02):
    for _ in range(round(seconds / dt)):
        s._step(dt, 0.0)


def _records(s):
    return [ln for ln in s._rec.lines if ln["kind"] == "record"]


def test_erg_bias_is_journaled(tmp_path, monkeypatch):
    async def scenario():
        s, _ = _session(tmp_path, monkeypatch, 6110)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "deux_blocs"}, 2)
        s._on_command("start", {}, 3)
        run(s, 30.0)
        block1 = [r for r in _records(s) if r["block"] == 1]
        assert block1 and all(r["erg_bias_pct"] == 0 for r in block1)
        run(s, 35.0)                      # bloc 2 commencé
        s._handle_input(InputEvent.PLUS_SHORT)
        s._handle_input(InputEvent.PLUS_SHORT)
        n = len(_records(s))
        run(s, 10.0)
        after = _records(s)[n:]
        assert after and all(r["block"] == 2 and r["erg_bias_pct"] == 4 for r in after)
        assert all(r["target_w"] == pytest.approx(round(250 * 0.8 * 1.04), abs=1) for r in after[3:])
        s._handle_input(InputEvent.MINUS_LONG)   # pause ERG
        n = len(_records(s))
        run(s, 5.0)
        assert all(r["erg_bias_pct"] is None and r["target_w"] is None for r in _records(s)[n:])
    asyncio.run(scenario())


def test_bias_is_null_in_sim(tmp_path, monkeypatch):
    async def scenario():
        s, _ = _session(tmp_path, monkeypatch, 6120)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 5.0)
        recs = _records(s)
        assert recs and all(r["erg_bias_pct"] is None for r in recs)
    asyncio.run(scenario())


def test_mock_trainer_drop_writes_device_lines(tmp_path, monkeypatch):
    async def scenario():
        s, driver = _session(tmp_path, monkeypatch, 6130)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 2.0)
        driver.connected = False
        run(s, 1.0)
        driver.connected = True
        run(s, 1.0)
        dev = [(ln["device"], ln["state"]) for ln in s._rec.lines if ln["kind"] == "device"]
        assert dev == [("trainer", "down"), ("trainer", "up")]
        assert all(ln["kind"] != "device" for ln in s._rec.records + s._rec.events)
    asyncio.run(scenario())


def test_writer_refuses_unknown_device_or_state(tmp_path):
    with JournalWriter(tmp_path / "j.jsonl") as w:
        w.device("hr", "down", 1.0)
        with pytest.raises(ValueError):
            w.device("montre", "down", 1.0)
        with pytest.raises(ValueError):
            w.device("hr", "lost", 1.0)
    lines = list(read_journal(tmp_path / "j.jsonl"))
    assert lines[-1] == {"kind": "device", "ts": 1.0, "device": "hr", "state": "down"}


T0 = 1_761_300_000.0   # octobre 2025 (le FIT refuse une date antérieure à 1989)


def _journal_with_devices(path: Path) -> None:
    with JournalWriter(path, route_id="demo") as w:
        w.event("start", T0 + 0.0)
        for i in range(60):
            if i == 10:
                w.device("trainer", "down", T0 + 10.5)
            if i == 14:
                w.device("trainer", "up", T0 + 14.0)
            if i == 20:
                w.device("hr", "down", T0 + 20.0)
            w.record(Record(ts=T0 + 0.0 + i, t=float(i), distance=5.0 * i, speed=5.0,
                            power=200.0, cadence=90.0, hr=130, alt=100.0))
        w.event("stop", T0 + 60.0)


def test_summary_devices_section(tmp_path):
    j = tmp_path / "s.jsonl"
    _journal_with_devices(j)
    out = compute_summary(load_session(j), 250.0)
    assert out["devices"] == {"trainer": {"drops": 1, "down_s": 3.5},
                              "hr": {"drops": 1, "down_s": 40.0}}   # jamais revenue : fin de séance


def test_recover_ignores_device_lines(tmp_path):
    """FIT identique, hors horodatage de création, avec ou sans les lignes `device`."""
    j = tmp_path / "s.jsonl"
    _journal_with_devices(j)
    stripped = tmp_path / "sans.jsonl"
    stripped.write_text("".join(ln + "\n" for ln in j.read_text().splitlines()
                                if json.loads(ln)["kind"] != "device"), encoding="utf-8")
    a, _ = journal_to_fit(j, tmp_path / "a.fit")
    b, _ = journal_to_fit(stripped, tmp_path / "b.fit")

    def body(p):
        from fit_tool.profile.messages.file_id_message import FileIdMessage
        return [r.to_bytes() for r in iter_records(p) if not isinstance(r.message, FileIdMessage)]
    assert body(a) == body(b)
    ra, rb = a.read_bytes(), b.read_bytes()
    assert len(ra) == len(rb)
    assert sum(x != y for x, y in zip(ra, rb)) <= 8   # time_created et somme de contrôle au plus


@pytest.mark.slow
def test_coupures_scenario_device_lines(tmp_path, monkeypatch):
    """Bluetooth simulé, scénario `coupures` jusqu'à 60 s : une coupure par appareil."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.drivers.trainer = cfg.drivers.input = cfg.drivers.hr = "sim"
    cfg.drivers.sim_scenario = "coupures"
    cfg.ipc.port_state, cfg.ipc.port_commands = 6140, 6141

    async def scenario():
        s = CoreSession(cfg, journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
        task = asyncio.create_task(s.run(autostart=True))
        await asyncio.sleep(62.0)
        s.stop_event.set()
        await asyncio.wait_for(task, 15)
        return s
    asyncio.run(scenario())
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    lines = [ln for ln in read_journal(journal) if ln.get("kind") == "device"]
    for dev in ("trainer", "click_minus", "hr"):
        states = [ln["state"] for ln in lines if ln["device"] == dev]
        downs = states.index("down")
        assert states[downs:] == ["down", "up"], (dev, states)
    out = compute_summary(load_session(journal), 250.0)["devices"]
    assert {k: v["drops"] for k, v in out.items() if v["drops"]} == \
        {"trainer": 1, "click_minus": 1, "hr": 1}
    # Durées attendues du scénario : trainer et ceinture reconnectés en ~2 s (réannonce 1 s,
    # attente 1 s, connexion), Click « − » rendormi de 40 à 50 s puis reconnecté.
    for dev, expected in (("trainer", 2.0), ("click_minus", 10.5), ("hr", 2.5)):
        assert abs(out[dev]["down_s"] - expected) <= 2.0, (dev, out[dev])
