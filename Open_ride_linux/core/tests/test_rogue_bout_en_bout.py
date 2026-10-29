"""Lot X40 : run Cyber-Rogue de bout en bout dans la vraie séance du core (outil `rogue_bout_en_bout`)."""

from __future__ import annotations

import json

import pytest

from openride_core.rogue import mode as rogue_mode
from openride_core.tools import rogue_bout_en_bout as tool


def failed(rep: tool.Report) -> list[str]:
    return [f"{label} : {detail}" for ok, label, detail in rep.checks if ok is False]


@pytest.mark.parametrize("objective", ["threshold", "vo2max"])
def test_full_run_passes_every_check(objective):
    rep = tool.run(objective, 30, seed=5)
    assert rep.ok, failed(rep)
    assert rep.phases[0] == "WARMUP" and rep.phases[-1] == "RESULTS" and "BOSS" in rep.phases
    assert rep.summary["result"] in ("victory", "defeat") and rep.summary["objective"] == objective
    assert rep.counts["room"] >= 2 and rep.counts["loot"] >= 1 and rep.counts["error"] == 0
    assert rep.wall_s < 30.0


def test_trace_holds_every_message_for_the_visual_bench(tmp_path):
    trace = tmp_path / "trace.jsonl"
    rep = tool.run("endurance", 30, seed=3, trace=trace)
    assert rep.ok, failed(rep)
    lines = [json.loads(ln) for ln in trace.read_text("utf-8").splitlines()]
    kinds = {ln["msg"]["type"] for ln in lines}
    assert {"state", "room", "loot", "input"} <= kinds
    ts = [ln["t"] for ln in lines]
    assert ts == sorted(ts)
    phases = {ln["msg"]["rogue"]["phase"] for ln in lines if ln["msg"]["type"] == "state" and ln["msg"].get("rogue")}
    assert {"WARMUP", "ROOM", "CORRIDOR", "BOSS", "COOLDOWN", "RESULTS"} <= phases
    last = [ln["msg"] for ln in lines if ln["msg"]["type"] == "state"][-1]
    assert last["session_state"] == "FINISHED" and last["summary"]["rogue"]


def test_session_left_running_after_results_is_caught(monkeypatch):
    """Défaut trouvé à la mise en service : la séance restait RUNNING après les résultats."""
    monkeypatch.setattr(rogue_mode, "RESULTS_HOLD_S", 1e9)
    rep = tool.run("threshold", 30, seed=5)
    assert len(failed(rep)) == 1 and failed(rep)[0].startswith("séance terminée d'elle-même")
    assert rep.summary["result"] in ("victory", "defeat")          # terminée par end_session, bilan intact


@pytest.mark.parametrize("args, msg", [
    (("sprint", 30), "objectif"), (("threshold", 20), "durée"), (("threshold", 30, 5, "pro"), "profil"),
])
def test_bad_call_is_named(args, msg):
    with pytest.raises(tool.RunError, match=msg):
        tool.run(*args)


def test_main_exit_codes(capsys):
    assert tool.main(["--objective", "sprint"]) == 2
    assert tool.main(["--objective", "threshold", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["ok"] and out[0]["phases"][-1] == "RESULTS"
