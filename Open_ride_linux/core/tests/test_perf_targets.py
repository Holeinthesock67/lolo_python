"""Budgets de performance par préréglage (lot X14) : perf_targets.json et verdict de la sonde."""

import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
spec = importlib.util.spec_from_file_location("perf_probe", TESTS / "perf_probe.py")
pp = importlib.util.module_from_spec(spec)
sys.modules["perf_probe"] = pp
spec.loader.exec_module(pp)


def rows(preset="medium", fps=60.0, p99=18.0, gpu=9.0, util=50.0, n=80, slow_start=True):
    out = []
    for i in range(n):
        warm = slow_start and i < 15   # chargement : 20 premières secondes ignorées
        out.append({"t_s": float(i), "fps": 20.0 if warm else fps, "frame_p99_ms": 150.0 if warm else p99,
                    "gpu_ms": 30.0 if warm else gpu, "gpu_util_pct": 99.0 if warm else util, "preset": preset})
    return out


def by_label(checks):
    return {label.split(" : ")[1]: (ok, msg) for ok, label, msg in checks}


def test_targets_follow_the_y13_budgets():
    t = pp.load_targets()
    assert t["warmup_s"] == 20
    assert t["presets"]["low"]["gpu_ms_median_max"] == 6 and t["presets"]["low"]["fps_median_min"] == 55
    assert t["presets"]["medium"]["fps_median_min"] == 58 and t["presets"]["medium"]["gpu_ms_median_max"] == 12
    assert t["presets"]["high"]["gpu_ms_median_max"] == 14
    assert all(p["p99_ms_max"] == 25 for p in t["presets"].values())


def test_within_budget_and_warmup_ignored():
    checks = by_label(pp.budget_checks(rows()))
    assert all(ok is True for ok, _ in checks.values()), checks
    assert checks["images/s"][1] == "médiane 60.0 (au moins 58)"
    assert checks["GPU saturé"][1].startswith("0.0 % des secondes au-dessus de 95 %")


def test_over_budget_fails_each_measure():
    checks = by_label(pp.budget_checks(rows(fps=50.0, p99=30.0, gpu=13.0, util=97.0)))
    assert [checks[k][0] for k in ("images/s", "temps d'image p99", "GPU de la vue", "GPU saturé")] == [False] * 4


def test_preset_read_from_probe_not_from_command_line():
    checks = pp.budget_checks(rows(preset="low", gpu=9.0))
    assert checks[2] == (False, "budget low : GPU de la vue", "médiane 9.00 ms (au plus 6 ms)")
    mixed = rows(preset="medium")[:40] + rows(preset="low")[40:]
    assert pp.budget_checks(mixed)[0][0] is False and "plusieurs préréglages" in pp.budget_checks(mixed)[0][2]


def test_xvfb_and_missing_nvidia_are_info():
    checks = pp.budget_checks(rows(fps=5.0), real_window=False)
    assert all(ok is None for ok, _, _ in checks)
    assert "indicatif sous Xvfb" in checks[0][2]
    no_gpu = [{k: v for k, v in r.items() if k != "gpu_util_pct"} for r in rows()]
    assert by_label(pp.budget_checks(no_gpu))["GPU saturé"] == (None, "pas de mesure (nvidia-smi absent)")


def test_report_writes_budgets_and_strict_exit_code(tmp_path):
    head = "t_s;unix_s;fps;frame_p99_ms;gpu_ms;preset"
    lines = [head] + [f"{i}.00;{1000 + i}.00;40.00;30.00;5.00;medium" for i in range(60)]
    src = tmp_path / "moteur.csv"
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r")]) == 0
    text = (tmp_path / "r" / "sonde.txt").read_text(encoding="utf-8")
    assert "[ÉCHEC] budget medium : images/s : médiane 40.0 (au moins 58)" in text
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r"), "--budgets"]) == 1
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r"), "--budgets", "--xvfb"]) == 0
