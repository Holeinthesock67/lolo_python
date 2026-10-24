"""Scénario de simulation tiré d'un journal du core (lot M5, `tools/log_scenario.py`)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.session import CoreSession
from openride_core.sim_scenarios import SCENARIOS, load_scenario
from openride_core.tools import log_scenario
from openride_core.tools.log_scenario import EXTRA_FORMAT_STRINGS, EXTRA_PATTERNS, convert, main

LOGS = Path(__file__).parent / "data" / "logs"
SRC = Path(__file__).parents[1] / "src" / "openride_core"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"   # celui de `__main__.py`


def _lines(name: str) -> list[str]:
    return (LOGS / name).read_text(encoding="utf-8").splitlines()


def test_extra_format_strings_exist_in_the_source():
    for key, (filename, fmt) in EXTRA_FORMAT_STRINGS.items():
        assert fmt in (SRC / filename).read_text(encoding="utf-8"), key


def test_extra_patterns_match_their_format():
    assert EXTRA_PATTERNS["hr_connected"].match("Ceinture cardio connectée (HRM-Dual:123)")
    assert EXTRA_PATTERNS["hr_disconnected"].match("Ceinture cardio déconnectée après 113.0 s")


def test_two_click_boxes_are_told_apart():
    spec, summary = convert(_lines("seance_deux_boitiers.log"))
    drops = [(e["t"], e["device"]) for e in spec["events"] if e["action"] == "drop"]
    assert drops == [(75.0, "click_minus"), (130.0, "click_plus"), (165.0, "trainer"), (180.0, "hr")]
    wakes = [(e["t"], e["device"]) for e in spec["events"] if e["action"] == "wake"]
    assert wakes == [(84.5, "click_minus"), (133.5, "click_plus")]
    assert spec["click"]["plus"]["appear_at"] == 3.5 and spec["click"]["minus"]["appear_at"] == 6.0
    att = [e for e in spec["events"] if e["action"] == "att_error"]
    assert att == [{"t": 100.0, "action": "att_error", "device": "trainer", "code": 0x80, "count": 1}]
    assert [e["t"] for e in spec["events"] if e["action"] == "control_lost"] == [150.0]
    presses = [e for e in spec["events"] if e["action"] == "press"]
    assert presses[0]["button"] == "+" and presses[1] == {
        "t": 30.0, "action": "press", "button": "-", "duration_s": 1.0}
    assert summary["ignored"]["perf"] == 1


def test_old_click_lines_without_address_use_the_last_box():
    spec, _ = convert(_lines("seance_click_coupures.log"))
    drops = [e for e in spec["events"] if e["action"] == "drop"]
    assert {e["device"] for e in drops if e["device"].startswith("click")} == {"click_plus"}
    silence = [e for e in spec["events"] if e["action"] == "silence"]
    assert silence and silence[0]["seconds"] > 0


def test_window_keeps_and_shifts_events():
    spec, summary = convert(_lines("seance_deux_boitiers.log"), t_from=70, t_to=140)
    assert [(e["t"], e["action"]) for e in spec["events"]] == [
        (5.0, "drop"), (14.5, "wake"), (30.0, "att_error"), (60.0, "drop"), (63.5, "wake")]
    assert summary["dropped_outside_window"] == 5
    assert spec["trainer"]["appear_at"] == 0.0   # connecté avant la fenêtre : présent d'emblée


def test_session_choice(tmp_path):
    two = _lines("seance_normale.log") + _lines("seance_deux_boitiers.log")
    spec, summary = convert(two, session=1)
    assert summary["sessions"] == 2 and "séance 1" in spec["description"]
    with pytest.raises(log_scenario.LogScenarioError, match="séance 3 absente"):
        convert(two, session=3)


@pytest.mark.parametrize("content", ["", "n'importe quoi\nsans horodatage\n",
                                     "\x00\xff garbage"])
def test_unusable_journal_exits_1(tmp_path, capsys, content):
    path = tmp_path / "x.log"
    path.write_text(content, encoding="utf-8", errors="replace")
    assert main([str(path)]) == 1
    err = capsys.readouterr().err
    assert "aucune séance" in err and "Traceback" not in err


def test_missing_journal_exits_1(tmp_path, capsys):
    assert main([str(tmp_path / "absent.log")]) == 1
    assert "lecture impossible" in capsys.readouterr().err


def _session(cfg: Config, tmp_path: Path, seconds: float, log_path: Path | None = None) -> None:
    handler = None
    if log_path is not None:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT))
        logging.getLogger().addHandler(handler)
    old_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.INFO)

    async def scenario():
        s = CoreSession(cfg, journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
        task = asyncio.create_task(s.run(autostart=True))
        await asyncio.sleep(seconds)
        s.stop_event.set()
        await asyncio.wait_for(task, 15)
    try:
        asyncio.run(scenario())
    finally:
        logging.getLogger().setLevel(old_level)
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            handler.close()


def _sim_cfg(scenario: str, port: int) -> Config:
    cfg = Config()
    cfg.drivers.trainer = cfg.drivers.input = cfg.drivers.hr = "sim"
    cfg.drivers.sim_scenario = scenario
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    return cfg


def test_generated_scenario_runs_as_a_file(tmp_path, monkeypatch, capsys):
    """Critère 4 : le scénario produit se charge par --sim-scenario FICHIER (séance de 20 s)."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    out = tmp_path / "panne.json"
    assert main([str(LOGS / "seance_deux_boitiers.log"), "-o", str(out), "--to", "18"]) == 0
    assert load_scenario(str(out))["trainer"]["appear_at"] == 1.5
    _session(_sim_cfg(str(out), 6210), tmp_path, 20.0)


@pytest.mark.slow
def test_roundtrip_with_coupures(tmp_path, monkeypatch):
    """Critère 2 : séance `coupures` → journal → scénario ; drop et control_lost à ± 1,5 s."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    log_path = tmp_path / "run.log"
    _session(_sim_cfg("coupures", 6220), tmp_path, 104.0, log_path)
    spec, _ = convert(log_path.read_text(encoding="utf-8").splitlines(), source=str(log_path))
    json.dumps(spec)
    want = [e for e in SCENARIOS["coupures"]["events"] if e["action"] in ("drop", "control_lost")]
    got = [e for e in spec["events"] if e["action"] in ("drop", "control_lost")]
    for w in want:
        match = [g for g in got if g["action"] == w["action"] and g.get("device") == w["device"]
                 and abs(g["t"] - w["t"]) <= 1.5]
        assert match, (w, got)
    assert any(e["action"] == "silence" for e in spec["events"])
