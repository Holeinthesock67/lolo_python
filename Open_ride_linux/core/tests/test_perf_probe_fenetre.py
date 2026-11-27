"""Fenêtre du roulage de la sonde (lot GF7, fil « Bilan des à-coups », 27 novembre) : écran de bilan, dérive
depuis le premier mètre et barre de préparation hors des totaux par cause."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pp = _load("perf_probe")

T0 = 1_000_000.0          # heure Unix du premier relevé
START, END = T0 + 60.0, T0 + 600.0   # premier mètre à 60 s, end_session à 600 s


def rows(n=660, gpu_load=30.0, gpu_ride=25.0):
    out = []
    for i in range(n):
        u = T0 + i
        out.append({"t_s": float(i), "unix_s": u, "fps": 60.0, "frame_max_ms": 20.0, "preset": "low",
                    "frame_p99_ms": gpu_load if u < START else gpu_ride})
    return out


def test_phase_of_window_edges():
    w = (START, END)
    assert pp.phase_of({"unix_s": START - 1}, w) == "avant"
    assert pp.phase_of({"unix_s": START}, w) == "roulage"
    assert pp.phase_of({"unix_s": END + 0.5}, w) == "après"
    assert pp.phase_of({"t_s": 3.0}, w) == "roulage"          # sans heure : gardée
    assert pp.phase_of({"unix_s": END + 9}, None) == "roulage"   # sans fenêtre : comme avant
    assert pp.phase_of({"unix_s": END + 9}, (None, END)) == "après"


def test_drift_starts_one_minute_after_first_metre():
    r = rows()
    # Sans fenêtre, la première minute est l'écran de chargement : dérive fausse de −5 ms.
    assert pp.summarize(r)["drift"]["frame_p99_ms"] == -5.0
    s = pp.summarize(r, (START, END))
    assert s["drift"]["frame_p99_ms"] == 0.0 and s["drift_window"] == "roulage"


def test_summary_screen_not_judged_but_reported(tmp_path):
    r = rows()
    for row in r:
        if row["unix_s"] > END:   # écran de bilan : images lentes
            row["frame_max_ms"] = 400.0
    without = pp.write_report(r, tmp_path / "a", real_window=True)
    assert any(ok is False and label == "à-coups : pire image" for ok, label, _ in without["budgets"])
    s = pp.write_report(r, tmp_path / "b", real_window=True, window=(START, END))
    checks = {label: (ok, msg) for ok, label, msg in s["budgets"]}
    assert checks["à-coups : pire image"][0] is True
    ok, msg = checks["à-coups : écran de bilan"]
    assert ok is None and "400 ms" in msg and "non jugé" in msg
    assert len(list((tmp_path / "b" / "sonde.csv").read_text().splitlines())) == len(r) + 1   # csv entier


def test_preparation_and_summary_out_of_cause_totals(tmp_path):
    d = tmp_path / "moteur"
    d.mkdir()
    sac = ["t_s;unix_s;frame_ms;distance_m;cause;steps"]
    sac += [f"{i}.0;{T0 + i:.1f};500.0;0.0;menu;menu affichage preparation" for i in range(5)]
    sac += [f"{100 + i}.0;{T0 + 100 + i:.1f};40.0;{300.0 + i:.1f};tuile;tuile near" for i in range(3)]
    sac += [f"{605 + i}.0;{END + 5 + i:.1f};80.0;5000.0;menu;menu affichage summary" for i in range(4)]
    (d / "saccades.csv").write_text("\n".join(sac) + "\n", encoding="utf-8")
    st = pp.stall_summary(pp.read_stalls(d), (START, END))
    assert st["count"] == 3 and list(st["causes"]) == ["tuile"]
    assert st["phases"]["avant"]["count"] == 5 and st["phases"]["après"]["count"] == 4
    text = pp.stall_text(st)
    assert "pendant le roulage" in text and "écran de bilan" in text and "préparation" in text
    # Sans fenêtre : tout compté comme avant.
    assert pp.stall_summary(pp.read_stalls(d))["count"] == 12


def test_riding_window_from_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["sim_bench.py"])
    sb = _load("sim_bench")
    j = tmp_path / "s.jsonl"
    j.write_text("\n".join(json.dumps(x) for x in (
        {"kind": "event", "event": "start", "ts": T0},
        {"kind": "record", "ts": T0 + 10, "distance": 0.0},
        {"kind": "record", "ts": T0 + 11, "distance": 0.4},
        {"kind": "record", "ts": START, "distance": 1.6},
        {"kind": "record", "ts": START + 1, "distance": 9.0})) + "\nnon json\n", encoding="utf-8")
    assert sb.riding_window(j, END) == (START, END)
    assert sb.riding_window(None, END) == (None, END)
    assert sb.riding_window(tmp_path / "absent.jsonl", None) is None
