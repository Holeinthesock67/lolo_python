"""À-coups de la sonde (saccades du 04/11 : une image de 82 à 147 ms tous les 40 m, invisible au p99) :
compte des images lentes, pire image et périodicité en distance (perf_probe.hitch_checks)."""

import importlib.util
import random
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "perf_probe.py"
spec = importlib.util.spec_from_file_location("perf_probe", SCRIPT)
pp = importlib.util.module_from_spec(spec)
sys.modules["perf_probe"] = pp
spec.loader.exec_module(pp)

SPEED_MPS = 8.33   # 30 km/h : un tronçon de 40 m toutes les 4,8 s


def rows(n=180, hitch_every_s=None, hitch_ms=120.0):
    out = []
    for i in range(n):
        slow = hitch_every_s is not None and i >= 20 and i % hitch_every_s == 0
        out.append({"t_s": float(i), "fps": 60.0, "frame_p99_ms": 18.0, "frame_max_ms": hitch_ms if slow else 18.0,
                    "preset": "medium"})
    return out


def saccades(distances, ms=110.0, cause="inconnue"):
    return [{"t_s": 20.0 + d / SPEED_MPS, "frame_ms": ms, "distance_m": float(d), "cause": cause} for d in distances]


def by_label(checks):
    return {label.split(" : ")[1]: (ok, msg) for ok, label, msg in checks}


def test_targets_have_hitch_limits():
    h = pp.load_targets()["hitches"]
    assert (h["hitch_ms"], h["max_per_min"], h["freeze_ms"]) == (50, 1, 100)


def test_period_of_the_40_m_chunks_found_not_its_half_or_double():
    d = [40.0 * k + random.Random(k).uniform(0.0, 0.6) for k in range(1, 29)]   # 40, 80 … 1120 m
    per = pp.hitch_period(d)
    assert per is not None and abs(per["period_m"] - 40.0) <= 1.0, per
    assert per["share"] == 1.0


def test_no_period_for_scattered_hitches():
    rng = random.Random(7)
    assert pp.hitch_period([rng.uniform(0.0, 3000.0) for _ in range(12)]) is None
    assert pp.hitch_period([100.0, 140.0, 180.0]) is None   # moins de 4 à-coups : rien à conclure


def test_bench_of_main_fails_on_the_40_m_hitches():
    sac = saccades(range(200, 1121, 40))
    checks = by_label(pp.hitch_checks(rows(hitch_every_s=5), sac))
    assert checks["images lentes"][0] is False and "par minute (au plus 1)" in checks["images lentes"][1]
    assert checks["pire image"] == (False, "120 ms (au plus 100 ms)")
    ok, msg = checks["périodicité en distance"]
    assert ok is False and "tous les 40." in msg and "causes : inconnue" in msg


def test_smooth_run_passes_and_captures_are_left_out():
    sac = saccades(range(200, 1121, 40), ms=140.0, cause="capture") + saccades([333.0], ms=60.0)
    checks = by_label(pp.hitch_checks(rows(), sac))
    assert all(ok is True for ok, _ in checks.values()), checks
    assert checks["pire image"][1] == "18 ms (au plus 100 ms)"


def test_warmup_ignored_and_xvfb_is_info():
    early = rows()
    early[5]["frame_max_ms"] = 900.0   # chargement du parcours
    assert by_label(pp.hitch_checks(early))["pire image"][0] is True
    checks = pp.hitch_checks(rows(hitch_every_s=5), saccades(range(200, 1121, 40)), real_window=False)
    assert all(ok is None for ok, _, _ in checks) and "indicatif sous Xvfb" in checks[0][2]


def test_report_lists_hitches_with_budgets(tmp_path):
    d = tmp_path / "moteur"
    d.mkdir()
    head = "t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;frame_max_ms;gpu_ms;preset"
    lines = [f"{i}.00;{1000 + i}.00;60.00;16.70;18.00;{120.0 if i >= 20 and i % 5 == 0 else 18.0:.2f};9.00;medium"
             for i in range(120)]
    (d / "moteur.csv").write_text("\n".join([head, *lines]) + "\n", encoding="utf-8")
    sac = [f"{20 + k * 4.8:.3f};1000.0;110.0;{200 + 40 * k:.1f};inconnue;herbe 600 2.1" for k in range(20)]
    (d / "saccades.csv").write_text("\n".join(["t_s;unix_s;frame_ms;distance_m;cause;steps", *sac]) + "\n",
                                    encoding="utf-8")
    summary = pp.write_report(pp.read_engine_csv(d / "moteur.csv"), tmp_path / "out", engine_dir=d)
    text = (tmp_path / "out" / "sonde.txt").read_text(encoding="utf-8")
    assert "À-coups" in text and "tous les 40." in text
    assert pp._budget_verdict(summary, True) == 1
