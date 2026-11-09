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
        slow = hitch_every_s is not None and i >= 30 and i % hitch_every_s == 0
        out.append({"t_s": float(i), "fps": 60.0, "frame_p99_ms": 18.0, "frame_max_ms": hitch_ms if slow else 18.0,
                    "preset": "medium"})
    return out


def saccades(distances, ms=110.0, cause="inconnue"):
    return [{"t_s": 30.0 + d / SPEED_MPS, "frame_ms": ms, "distance_m": float(d), "cause": cause} for d in distances]


def by_label(checks):
    return {label.split(" : ")[1]: (ok, msg) for ok, label, msg in checks}


def test_targets_have_hitch_limits():
    h = pp.load_targets()["hitches"]
    assert (h["warmup_s"], h["hitch_ms"], h["max_per_min"], h["freeze_ms"], h["start_freeze_ms"]) == (30, 50, 3, 100, 150)


def test_period_of_the_40_m_chunks_found_not_its_half_or_double():
    d = [40.0 * k + random.Random(k).uniform(0.0, 0.6) for k in range(1, 29)]   # 40, 80 … 1120 m
    per = pp.hitch_period(d)
    assert per is not None and abs(per["period_m"] - 40.0) <= 1.0, per
    assert per["share"] == 1.0


def test_no_period_for_scattered_hitches():
    rng = random.Random(7)
    assert pp.hitch_period([rng.uniform(0.0, 3000.0) for _ in range(12)]) is None
    assert pp.hitch_period([100.0, 140.0, 180.0]) is None   # moins de 4 à-coups : rien à conclure


def test_period_counts_passes_not_frames():
    """Lot X57 : chaque passage de 40 m compte une fois, même s'il donne plusieurs images lentes."""
    d = [40.0 * k + 0.1 * j for k in range(5, 29) for j in range(3)]   # 3 images lentes par tronçon
    per = pp.hitch_period(d)
    assert per is not None and abs(per["period_m"] - 40.0) <= 1.0, per
    assert (per["hits"], per["passes"]) == (72.0, 24.0)


def test_two_far_apart_bursts_are_not_a_period():
    """r735c low (07/11) : deux paquets de 6 et 7 images à ~780 m l'un de l'autre, plus deux isolées, sur
    2,5 km. L'ancien contrôle, qui comptait les images, y voyait une image lente tous les 778 m."""
    d = ([1614.0 + 25.0 * i for i in range(6)] + [2402.0 + 7.0 * i for i in range(7)]
         + [2263.0, 2270.0] + [320.0, 905.0, 1180.0])
    assert pp.hitch_period(d) is None


def test_a_burst_at_the_finish_is_not_a_period():
    """Séance FTP du 04/11 : 17 images lentes à 5 000 m (cycliste arrêté à l'arrivée), soit un seul passage,
    plus quelques-unes éparses : l'ancien contrôle y voyait une période de 293 m."""
    d = [130.2, 188.5, 289.4, 884.0, 1263.9, 1336.1, 1373.3, 1473.8, 2220.9, 2320.7, 2408.4, 2527.2,
         2565.4, 2627.5, 2637.0, 3526.9, 4001.5, 4345.4] + [5000.0] * 17
    assert pp.hitch_period(d) is None


def test_window_across_the_end_of_the_turn_counts_one_pass():
    """Phase à cheval sur la fin du tour (39,9 puis 40,1 m pour P = 40) : les deux comptent comme un passage."""
    d = [40.0 * k + (-0.1 if k % 2 else 0.1) for k in range(1, 20)]
    per = pp.hitch_period(d)
    assert per is not None and abs(per["period_m"] - 40.0) <= 1.0 and per["passes"] >= 18, per


def test_bench_of_main_fails_on_the_40_m_hitches():
    sac = saccades(range(200, 1121, 40))
    checks = by_label(pp.hitch_checks(rows(hitch_every_s=5), sac))
    assert checks["images lentes"][0] is False and "par minute (au plus 3)" in checks["images lentes"][1]
    assert checks["pire image"] == (False, "120 ms (au plus 100 ms)")
    ok, msg = checks["périodicité en distance"]
    assert ok is False and "tous les 40." in msg and "causes : inconnue" in msg
    assert "(17 images sur 17, revenue à 17 passages" in msg


def test_smooth_run_passes_and_captures_are_left_out():
    sac = saccades(range(200, 1121, 40), ms=140.0, cause="capture") + saccades([333.0], ms=60.0)
    checks = by_label(pp.hitch_checks(rows(), sac))
    assert all(ok is True for ok, _ in checks.values()), checks
    assert checks["pire image"][1] == "18 ms (au plus 100 ms)"


def test_isolated_hitches_of_a_short_bench_pass():
    """Banc de 2 min de #710 sur la demo intégrée medium : deux images de 50 et 58 ms, sans période."""
    r = rows(n=113)
    r[77]["frame_max_ms"], r[111]["frame_max_ms"] = 50.4, 57.5
    sac = saccades([510.0, 760.0], ms=57.0)
    assert all(ok is True for ok, _, _ in pp.hitch_checks(r, sac))


def test_warmup_ignored_and_xvfb_is_info():
    early = rows()
    early[5]["frame_max_ms"] = 900.0   # chargement du parcours
    early[25]["frame_max_ms"] = 147.0  # arbres des premières tuiles, au départ (banc #710 du 04/11)
    checks = by_label(pp.hitch_checks(early))
    assert checks["pire image"][0] is True
    assert checks["départ"] == (True, "pire image 147 ms de 20 à 30 s (au plus 150 ms)")
    early[25]["frame_max_ms"] = 400.0  # départ figé : jugé à part, pas caché par le régime établi
    assert by_label(pp.hitch_checks(early))["départ"][0] is False
    checks = pp.hitch_checks(rows(hitch_every_s=5), saccades(range(200, 1121, 40)), real_window=False)
    assert all(ok is None for ok, _, _ in checks) and "indicatif sous Xvfb" in checks[0][2]


def test_slow_seconds_before_the_first_metre_or_of_a_capture_are_not_steady():
    """Banc PC de #716 (peloton, high) : chargement de 35 s, images de 135 ms à 0 m après warmup_s et pendant une
    capture : jugées avec le départ (150 ms) ou écartées ; une image lente en roulant reste jugée."""
    r = rows()
    r[34]["frame_max_ms"], r[36]["frame_max_ms"] = 135.0, 140.0
    sac = [{"t_s": 34.1, "frame_ms": 135.0, "distance_m": 0.0, "cause": "inconnue"},
           {"t_s": 36.2, "frame_ms": 140.0, "distance_m": 69.1, "cause": "capture"}]
    checks = by_label(pp.hitch_checks(r, sac))
    assert checks["pire image"] == (True, "18 ms (au plus 100 ms)")
    assert checks["départ"] == (True, "pire image 135 ms de 20 à 30 s et avant le premier mètre (au plus 150 ms)")
    sac[0]["distance_m"] = 12.0   # en roulant : à-coup du régime établi
    assert by_label(pp.hitch_checks(r, sac))["pire image"] == (False, "135 ms (au plus 100 ms)")


def test_hitches_before_the_first_metre_make_no_period():
    """Banc PC de #716 (aaf4b6ac, high) : quatre images lentes à 0 m pendant un chargement long, puis une à 305 m,
    donnaient « tous les 76,5 m » ; celles d'avant le premier mètre sont du départ, pas une période."""
    sac = [{"t_s": t, "frame_ms": 60.0, "distance_m": 0.0, "cause": "inconnue"} for t in (31.0, 35.0, 40.0, 50.0)]
    sac += [{"t_s": 50.5, "frame_ms": 50.3, "distance_m": 0.2, "cause": "bots"},
            {"t_s": 99.0, "frame_ms": 58.3, "distance_m": 304.8, "cause": "inconnue"}]
    sac.insert(0, {"t_s": 4.0, "frame_ms": 149.0, "distance_m": 0.0, "cause": "inconnue"})
    assert by_label(pp.hitch_checks(rows(), sac))["périodicité en distance"][0] is True


def test_report_lists_hitches_with_budgets(tmp_path):
    d = tmp_path / "moteur"
    d.mkdir()
    head = "t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;frame_max_ms;gpu_ms;preset"
    lines = [f"{i}.00;{1000 + i}.00;60.00;16.70;18.00;{120.0 if i >= 30 and i % 5 == 0 else 18.0:.2f};9.00;medium"
             for i in range(120)]
    (d / "moteur.csv").write_text("\n".join([head, *lines]) + "\n", encoding="utf-8")
    sac = [f"{30 + k * 4.8:.3f};1000.0;110.0;{200 + 40 * k:.1f};inconnue;herbe 600 2.1" for k in range(20)]
    (d / "saccades.csv").write_text("\n".join(["t_s;unix_s;frame_ms;distance_m;cause;steps", *sac]) + "\n",
                                    encoding="utf-8")
    summary = pp.write_report(pp.read_engine_csv(d / "moteur.csv"), tmp_path / "out", engine_dir=d)
    text = (tmp_path / "out" / "sonde.txt").read_text(encoding="utf-8")
    assert "À-coups" in text and "tous les 40." in text
    assert pp._budget_verdict(summary, True) == 1
