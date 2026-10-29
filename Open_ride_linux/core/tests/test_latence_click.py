"""Latence appui Click → commande → écran (lot X7) : journal du core, champs IPC, statistique de log_report."""

import json
import logging
from pathlib import Path

import jsonschema
import pytest

from openride_core import latency_log
from openride_core.config import from_dict
from openride_core.tools import log_report

SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc" / "input.schema.json"


@pytest.fixture(autouse=True)
def _reset():
    latency_log.enable(False)
    yield
    latency_log.enable(False)


def lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "latence"]


def test_nothing_without_the_option(caplog):
    caplog.set_level(logging.DEBUG, logger="latence")
    provider = object()
    latency_log.new_press(provider)
    with latency_log.handling(provider) as press_id:
        assert press_id is None and latency_log.ipc_fields() == {}
        latency_log.expect_cp()
    latency_log.cp_written()
    assert lines(caplog) == []


def test_one_line_per_stage_and_press(caplog):
    caplog.set_level(logging.INFO, logger="latence")
    latency_log.enable()
    plus, minus = object(), object()
    latency_log.new_press(plus)
    latency_log.new_press(minus)
    latency_log.new_press(plus)
    with latency_log.handling(plus) as first:
        fields = latency_log.ipc_fields()
        latency_log.expect_cp()
    with latency_log.handling(minus) as second:
        latency_log.ipc_fields()          # appui de menu : pas de Control Point attendu
    with latency_log.handling(plus) as third:
        latency_log.expect_cp()
    latency_log.cp_written()
    latency_log.cp_written()              # deuxième écriture : plus personne n'attend
    assert (first, second, third) == (1, 2, 3)
    assert fields["latence_id"] == 1 and fields["latence_t"] > 1.7e9
    stages = [(int(m.split("id=")[1].split()[0]), m.split("etage=")[1].split()[0]) for m in lines(caplog)]
    assert stages == [(1, "notif"), (2, "notif"), (3, "notif"), (1, "evenement"), (1, "ipc"),
                      (2, "evenement"), (2, "ipc"), (3, "evenement"), (1, "cp"), (3, "cp")]


def test_stale_control_point_wait_is_dropped(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="latence")
    latency_log.enable()
    p = object()
    latency_log.new_press(p)
    with latency_log.handling(p):
        latency_log.expect_cp()
    clock = latency_log.time.monotonic() + latency_log.CP_WINDOW_S + 1.0
    monkeypatch.setattr(latency_log.time, "monotonic", lambda: clock)
    latency_log.cp_written()
    assert not any("etage=cp" in m for m in lines(caplog))


def test_input_message_fields_follow_the_contract():
    latency_log.enable()
    p = object()
    latency_log.new_press(p)
    with latency_log.handling(p):
        msg = {"type": "input", "v": 1, "event": "PLUS_SHORT", **latency_log.ipc_fields()}
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert not list(validator.iter_errors(msg))
    assert list(validator.iter_errors({**msg, "latence_id": "1"}))


def test_config_key():
    assert from_dict({}).log.latence is False
    assert from_dict({"log": {"latence": True}}).log.latence is True


CORE = """2026-10-28 10:00:00 INFO latence: [latence] id=1 etage=notif t=1000.000000
2026-10-28 10:00:00 INFO latence: [latence] id=1 etage=evenement t=1000.010000
2026-10-28 10:00:00 INFO latence: [latence] id=1 etage=ipc t=1000.011000
2026-10-28 10:00:00 INFO latence: [latence] id=1 etage=cp t=1000.040000
2026-10-28 10:00:01 INFO latence: [latence] id=2 etage=notif t=1001.000000
2026-10-28 10:00:01 INFO latence: [latence] id=2 etage=evenement t=1001.020000
2026-10-28 10:00:01 INFO latence: [latence] id=2 etage=ipc t=1001.021000
2026-10-28 10:00:02 INFO latence: [latence] id=3 etage=notif t=1002.000000
2026-10-28 10:00:02 INFO latence: [latence] id=3 etage=evenement t=1002.030000
"""
ENGINE = """[latence] id=1 etage=recu t=1000.015000
[latence] id=1 etage=affiche t=1000.061000
[latence] id=2 etage=recu t=1001.031000
[latence] id=2 etage=affiche t=1001.121000
[latence] id=2 etage=affiche t=1001.500000
"""


def test_log_report_pairs_by_id_and_counts_incomplete_presses():
    rep = log_report.latency_report(CORE.splitlines(), ENGINE.splitlines())
    assert (rep["presses"], rep["complete"], rep["incomplete"]) == (3, 2, 1)
    assert rep["missing_stages"] == {"ipc": 1, "cp": 1, "recu": 1, "affiche": 1}
    e2e = rep["hops"]["bout en bout (notification → image)"]
    assert (e2e["count"], e2e["median_ms"], e2e["max_ms"]) == (2, 91.0, 121.0)   # 61 et 121 ms ; affiche répété : le premier
    assert rep["hops"]["événement → Control Point"] == {"count": 1, "median_ms": 30.0, "p95_ms": 30.0, "max_ms": 30.0}
    assert rep["hops"]["notification → événement"]["count"] == 3


def test_log_report_command(tmp_path, capsys):
    core, engine = tmp_path / "core.log", tmp_path / "engine.log"
    core.write_text(CORE)
    engine.write_text(ENGINE)
    assert log_report.main(["--latence", str(core), str(engine)]) == 0
    out = capsys.readouterr().out
    assert "3 appui(s), 2 apparié(s) de bout en bout, 1 incomplet(s)" in out
    assert log_report.main(["--json", "--latence", str(core), str(engine)]) == 0
    assert json.loads(capsys.readouterr().out)["complete"] == 2
    assert log_report.main(["--latence", str(core), str(tmp_path / "absent.log")]) == 1
