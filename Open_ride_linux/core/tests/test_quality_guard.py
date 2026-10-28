"""Garde-fou de la qualité réellement appliquée (lot X32) : journal de l'engine et sonde de performance."""

import importlib.util
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


qg = _load("quality_guard")
pp = _load("perf_probe")


def applied(q: str, requested: str, source: str) -> str:
    return f"Qualité appliquée : {q} (demandée {requested}, source {source})\n"


def shot(q: str | None, tag: str = "t003") -> str:
    data = {"tag": tag, "ok": True, "fps": 60}
    if q is not None:
        data["quality"] = q
    return f"[test] screenshot {json.dumps(data)}\n"


def test_medium_kept_until_the_end_passes():
    log = applied("medium", "medium", "cli") + shot("medium") + shot("medium", "t018")
    ok, msg = qg.check(log, "medium")
    assert ok is True
    assert "medium appliquée (2 capture(s))" in msg


def test_core_setting_back_to_low_fails_like_the_481_bug():
    # Le défaut du 28 octobre : --quality=medium, puis le core renvoie [render] quality = "low".
    log = applied("medium", "medium", "cli") + applied("low", "low", "reglage") + shot("low") + shot("low", "t018")
    ok, msg = qg.check(log, "medium")
    assert ok is False
    assert "qualité demandée medium, appliquée low (2/2 capture(s))" in msg
    assert "source reglage" in msg


def test_old_screenshots_without_field_use_the_last_applied_line():
    log = applied("medium", "medium", "cli") + shot(None) + applied("high", "high", "reglage") + shot(None)
    assert qg.qualities_at_captures(log) == ["medium", "high"]
    ok, _ = qg.check(log, "medium")
    assert ok is False


def test_without_captures_the_last_applied_line_decides():
    assert qg.check(applied("low", "low", "defaut"), "low")[0] is True
    assert qg.check(applied("low", "low", "defaut") + applied("high", "high", "reglage"), "low")[0] is False


def test_engine_log_without_quality_lines_is_unknown_not_ok():
    ok, msg = qg.check("hello_ack reçu\n", "medium")
    assert ok is None
    assert "aucune ligne" in msg


def test_unknown_setting_value_keeps_the_applied_quality():
    # Réglage inconnu reçu du core : la ligne dit ce qui reste appliqué.
    log = applied("medium", "medium", "cli") + applied("medium", "ultra", "reglage") + shot("medium")
    assert qg.check(log, "medium")[0] is True
    assert qg.applied_sequence(log)[-1] == ("medium", "ultra", "reglage")


def test_command_line_exit_codes(tmp_path, capsys):
    log = tmp_path / "engine.log"
    log.write_text(applied("low", "low", "reglage"), encoding="utf-8")
    assert qg.main([str(log), "low"]) == 0
    assert qg.main([str(log), "high"]) == 1
    log.write_text("rien\n", encoding="utf-8")
    assert qg.main([str(log), "low"]) == 2
    assert qg.main([]) == 2
    assert "ÉCHEC" in capsys.readouterr().out


def test_probe_presets_and_quality_check():
    rows = [{"t_s": float(i), "preset": "medium" if i < 5 else "low"} for i in range(10)]
    assert pp.presets_of(rows) == ["medium", "low"]
    ok, msg = pp.quality_check({"presets": pp.presets_of(rows)}, "medium")
    assert ok is False
    assert msg == "qualité voulue medium, mesurée en medium, puis low"
    assert pp.quality_check({"presets": ["high"]}, "high") == (True, "high sur toute la mesure")
    assert pp.quality_check({"presets": []}, "low")[0] is False


def test_probe_report_returns_failure_on_wrong_quality(tmp_path):
    head = "t_s;unix_s;fps;frame_p50_ms;frame_p99_ms;vram_mb;trees;preset"
    lines = [head] + [f"{i + 1}.00;{1000 + i}.00;60.00;16.60;20.00;300.00;1000;low" for i in range(5)]
    src = tmp_path / "moteur.csv"
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r"), "--quality", "low"]) == 0
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r"), "--quality", "medium"]) == 1
    assert "Préréglage low." in (tmp_path / "r" / "rapport.html").read_text(encoding="utf-8")
