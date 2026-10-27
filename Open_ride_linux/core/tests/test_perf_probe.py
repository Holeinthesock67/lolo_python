"""Sonde de performance du moteur, côté système (lot X13) : lecture, recalage, résumé, rapport."""

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "perf_probe.py"
spec = importlib.util.spec_from_file_location("perf_probe", SCRIPT)
pp = importlib.util.module_from_spec(spec)
sys.modules["perf_probe"] = pp
spec.loader.exec_module(pp)

HEAD = "t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;vram_mb;trees;preset"


def engine_csv(path: Path, n: int, t0: float = 1_000_000.0, vram_growth: float = 0.0) -> Path:
    lines = [HEAD]
    for i in range(n):
        lines.append(f"{i + 1:.2f};{t0 + i + 1:.2f};60.00;16.60;{20 + (i % 50 == 0) * 30:.2f};"
                     f"{300 + vram_growth * i:.2f};{1000 + i};low")
    lines.append("999;1")   # ligne en cours d'écriture : ignorée
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_read_engine_csv_skips_partial_line(tmp_path):
    rows = pp.read_engine_csv(engine_csv(tmp_path / "m.csv", 3))
    assert len(rows) == 3
    assert rows[0]["fps"] == 60.0 and rows[0]["preset"] == "low"
    assert pp.read_engine_csv(tmp_path / "absent.csv") == []


def test_parse_nvidia():
    assert pp.parse_nvidia("37, 812, 6144, 54, 1708\n") == {
        "gpu_util_pct": 37.0, "gpu_mem_mb": 812.0, "gpu_mem_total_mb": 6144.0, "gpu_temp_c": 54.0,
        "gpu_clock_mhz": 1708.0}
    assert pp.parse_nvidia("37, [N/A], 6144, 54, 1708")["gpu_util_pct"] == 37.0
    assert pp.parse_nvidia("") is None and pp.parse_nvidia("erreur") is None


def test_merge_aligns_on_wall_clock(tmp_path):
    rows = pp.read_engine_csv(engine_csv(tmp_path / "m.csv", 6))
    system = [{"unix_s": 1_000_000.0 + t, "gpu_util_pct": float(t)} for t in (1.2, 2.1, 3.0, 9.0)]
    merged = pp.merge(rows, system)
    assert [m.get("gpu_util_pct") for m in merged] == [1.2, 2.1, 3.0, 3.0, None, None]   # rien à ± 1,5 s
    assert pp.merge([], system)[1]["t_s"] == system[1]["unix_s"] - system[0]["unix_s"]


def test_summary_and_drift(tmp_path):
    rows = pp.read_engine_csv(engine_csv(tmp_path / "m.csv", 300, vram_growth=0.5))
    s = pp.summarize(rows)
    assert s["rows"] == 300 and 298 < s["duration_s"] < 300
    assert s["stats"]["fps"]["p50"] == 60.0 and s["stats"]["frame_p99_ms"]["max"] == 50.0
    assert 115 < s["drift"]["vram_mb"] < 125   # 0,5 Mo/s sur 4 min environ
    text = pp.summary_text(s, "Essai")
    assert "images/s" in text and "Dérive" in text and "mémoire vidéo (Godot) : +" in text
    short = pp.summarize(rows[:60])
    assert short["drift"] == {} and "moins de 2 min" in pp.summary_text(short, "Essai")


def test_write_report_and_cli(tmp_path):
    rows = pp.read_engine_csv(engine_csv(tmp_path / "m.csv", 30))
    out = tmp_path / "rapport"
    pp.write_report(rows, out, "Essai")
    page = (out / "rapport.html").read_text(encoding="utf-8")
    assert page.count("<svg") >= 3 and "Temps d" in page and "Arbres" in page
    assert (out / "sonde.csv").read_text(encoding="utf-8").startswith("t_s;unix_s;fps")
    (out / "rapport.html").unlink()
    assert pp.main(["report", str(out)]) == 0 and (out / "rapport.html").is_file()
    assert pp.main(["report", str(tmp_path / "vide.csv")]) == 1


def test_system_sampler_follows_a_process(tmp_path):
    """Un processus qui calcule : CPU proche d'un cœur, mémoire résidente lue dans /proc."""
    script = tmp_path / "openride_sonde_test.py"
    script.write_text("import time\nt = time.time()\nwhile time.time() - t < 5:\n    pass\n")
    busy = subprocess.Popen([sys.executable, str(script)])
    try:
        time.sleep(0.2)
        assert pp.find_pids(("openride_sonde_test",)) == [busy.pid]
        sampler = pp.SystemSampler(processes={"test": ("openride_sonde_test",), "absent": ("aucun_processus",)})
        first = sampler.sample()
        time.sleep(0.6)
        row = sampler.sample()
    finally:
        busy.kill()
        busy.wait()
    assert "test_cpu_pct" not in first and first["test_rss_mb"] > 1.0
    assert row["test_cpu_pct"] > 20.0
    assert "absent_rss_mb" not in row
    assert pp.proc_times(os.getpid())[1] > 1.0


def test_watch_stops_when_engine_stops_writing(tmp_path, monkeypatch):
    csv = engine_csv(tmp_path / "m.csv", 5, t0=time.time() - 5)
    monkeypatch.setattr(pp, "nvidia_sample", lambda: {"gpu_util_pct": 40.0})
    assert pp.watch(csv, tmp_path / "out", duration_s=None, wait_s=1.0, idle_stop_s=1.5) == 0
    data = (tmp_path / "out" / "sonde.csv").read_text(encoding="utf-8")
    assert "gpu_util_pct" in data
    assert pp.watch(tmp_path / "absent.csv", tmp_path / "o2", None, wait_s=0.5) == 1
