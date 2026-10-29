"""Suivi en direct d'un essai guidé dans une fenêtre à part (lot X45)."""

import io
import json

from openride_core.tools import suivi_direct as sd
from openride_core.tools import trainer_steps as ts
from openride_core.tools.guide import Guide


def quiet(title="Suivi"):
    return Guide(title, sound=False, screen=False, out=io.StringIO())


def test_guide_publishes_its_screen(tmp_path):
    live = tmp_path / "live.json"
    g = Guide("Banc", sound=False, screen=False, out=io.StringIO(), live_file=live)
    g.step("SIM 470 W", 12, "garde 85 rpm", index=2, total=7)
    g.tick({"puissance": "462 W", "cadence": "84 rpm"})
    g.publish(force=True)
    st = json.loads(live.read_text(encoding="utf-8"))
    assert st["step"]["text"] == "SIM 470 W" and st["step"]["index"] == 2 and 0 < st["step"]["remaining_s"] <= 12
    assert st["live"]["puissance"] == "462 W" and st["verdict"] is None
    g.alert("Plafond dépassé", beep=False)
    g.measure("palier 2", "t90 2.4", "s")
    g.finish(True, "Essai fini")
    st = json.loads(live.read_text(encoding="utf-8"))
    assert st["verdict"] == {"ok": True, "text": "Essai fini"} and st["measures"][0][0].startswith("palier 2")
    assert not live.with_suffix(".tmp").exists()


def test_viewer_replays_steps_alerts_and_verdict():
    clock = [1000.0]
    v = sd.Viewer(quiet(), now=lambda: clock[0])
    base = {"title": "Banc", "updated": 1000.0, "live": {"puissance": "150 W"}, "banner": "", "panel": [],
            "panel_ok": None, "measures": [], "notes": [], "verdict": None,
            "step": {"text": "SIM 150 W", "detail": "", "index": 1, "total": 3, "remaining_s": 40.0}}
    v.apply(base)
    assert v.g.step_.text == "SIM 150 W" and v.g.live["puissance"] == "150 W" and v.g.remaining() > 39
    v.apply({**base, "banner": "Cadence 70 rpm", "measures": [["palier 1 : t90 2 s", None]]})
    assert v.g.banner == "Cadence 70 rpm" and len(v.g.measures) == 1
    v.apply({**base, "measures": [["palier 1 : t90 2 s", None]]})
    assert v.g.banner == "" and len(v.g.measures) == 1       # pas de doublon
    clock[0] = 1010.0                                           # essai muet depuis 10 s
    v.apply({**base, "measures": [["palier 1 : t90 2 s", None]]})
    assert v.g.banner.startswith("Plus de nouvelles de l'essai")
    v.apply({**base, "updated": 1010.0, "verdict": {"ok": True, "text": "Essai fini"}, "notes": ["Décrochage à 31 s"]})
    assert v.finished and v.g.verdict == (True, "Essai fini") and v.g.notes == ["Décrochage à 31 s"]


def test_follow_keeps_the_window_until_enter(tmp_path):
    live = tmp_path / "live.json"
    assert sd.follow(live, quiet(), once=True) == 1                 # rien à suivre
    g = Guide("Banc", sound=False, screen=False, out=io.StringIO(), live_file=live)
    g.step("SIM 150 W", 5)
    g.finish(False, "Essai interrompu")
    asked = []
    assert sd.follow(live, quiet(), ask=lambda prompt: asked.append(prompt) or "") == 0
    assert asked and "Entrée pour fermer" in asked[0]
    assert sd.live_path(tmp_path) == live and sd.main([str(tmp_path), "--une-fois"]) == 0


def test_launch_uses_a_terminal_or_says_how(tmp_path, monkeypatch):
    live = tmp_path / "live.json"
    monkeypatch.delenv("OPENRIDE_TERMINAL", raising=False)
    assert sd.launch(live, which=lambda name: None) is None
    seen = []
    cmd = sd.launch(live, which=lambda name: "/usr/bin/xterm" if name == "xterm" else None, spawn=seen.append)
    assert seen[0][:2] == ["xterm", "-e"] and seen[0][-1] == str(live) and "suivi_direct" in cmd
    monkeypatch.setenv("OPENRIDE_TERMINAL", "mon-terminal --titre Suivi -- {cmd}")
    sd.launch(live, spawn=seen.append)
    assert seen[1][:4] == ["mon-terminal", "--titre", "Suivi", "--"] and seen[1][-1] == str(live)


def test_bench_window_on_the_simulated_trainer(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENRIDE_TERMINAL", "true {cmd}")
    out = tmp_path / "essai"
    assert ts.main(["--mode", "erg_paliers", "--trainer", "sim", "--fast", "--muet", "--fenetre",
                    "--out", str(out)]) == 0
    st = json.loads((out / "live.json").read_text(encoding="utf-8"))
    assert st["verdict"]["ok"] and st["title"].startswith("Banc de latence")
