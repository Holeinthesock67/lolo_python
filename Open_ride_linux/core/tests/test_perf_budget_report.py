"""Rapport des budgets de l'engine par machine (lot X19) : lecture des lignes [PERF] et du CSV, marges."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "perf_budget_report.py"
spec = importlib.util.spec_from_file_location("perf_budget_report", SCRIPT)
pbr = importlib.util.module_from_spec(spec)
sys.modules["perf_budget_report"] = pbr
spec.loader.exec_module(pbr)

# Lignes telles que perf_budget.gd les écrit dans un passage de run_engine_tests.sh.
RUN = """\
== Tests unitaires (tests/unit/, lot K1) ==
[PERF] passersby_frame : 0.15 ms, budget 0.20 ms
[PERF] sky_clouds_frame : 0.20 ms, budget 0.05 ms (DÉPASSÉ)
[OK] autre ligne
[PERF] sound_generation_memory : 9216.00 Ko, budget 16384.00 Ko
[PERF] nouveau_banc : 3.00 ms, budget inf ms
"""


def test_parse_perf_lines():
    m = pbr.parse(RUN.splitlines())
    assert m["passersby_frame"] == {"valeur": 0.15, "budget": 0.2, "unite": "ms"}
    assert m["sound_generation_memory"]["unite"] == "Ko"
    assert m["nouveau_banc"]["budget"] == float("inf")
    assert "autre" not in " ".join(m)


def test_parse_csv_keeps_last_measure():
    csv = ["2026-10-28_10:00:00;passersby_frame;0.30;0.20;oui;ms",
           "2026-10-28_11:00:00;passersby_frame;0.12;0.20;non;ms",
           "2026-10-28_11:00:00;tree_tile_high;140;150;non"]          # CSV d'avant X19, sans unité
    m = pbr.parse(csv)
    assert m["passersby_frame"]["valeur"] == 0.12
    assert m["tree_tile_high"]["unite"] == "ms"


def test_report_margins_and_missing():
    budgets = {"passersby_frame": {"budget_ms": 0.2}, "sky_clouds_frame": {"budget_ms": 0.05},
               "sound_generation_memory": {"budget_kb": 16384},
               "sound_synthesis_rogue_memory": {"budget_kb": 8192}}
    rows = {r["nom"]: r for r in pbr.report(pbr.parse(RUN.splitlines()), budgets)}
    assert rows["passersby_frame"]["etat"] == "OK" and round(rows["passersby_frame"]["marge_pct"]) == 25
    assert rows["sky_clouds_frame"]["etat"] == "DÉPASSÉ" and rows["sky_clouds_frame"]["marge_pct"] < 0
    assert rows["sound_generation_memory"]["etat"] == "OK"
    assert rows["sound_synthesis_rogue_memory"] == {"nom": "sound_synthesis_rogue_memory", "etat": "non mesuré",
                                                    "unite": "Ko", "lot": ""}
    assert rows["nouveau_banc"]["etat"] == "sans budget" and rows["nouveau_banc"]["marge_pct"] is None
    text = pbr.format_rows(list(rows.values()))
    assert text.splitlines()[0] == "Budgets de l'engine : 4 mesurés sur 5, 1 dépassement(s)"
    assert "[DÉPASSÉ] sky_clouds_frame" in text.splitlines()[1]     # le plus serré d'abord
    assert text.endswith("Non mesurés : sound_synthesis_rogue_memory")


def test_declared_budgets_file_is_coherent():
    budgets = pbr.declared()
    assert "sound_synthesis_rogue" in budgets and budgets["sound_synthesis_rogue"]["budget_ms"] == 300
    assert budgets["sound_synthesis_rogue_memory"]["budget_kb"] == 8192
    for name, entry in budgets.items():
        has_ms, has_kb = "budget_ms" in entry, "budget_kb" in entry
        assert has_ms != has_kb, f"{name} : un seul budget, en ms ou en Ko"
        ci = entry.get("ci_ms" if has_ms else "ci_kb")
        assert ci is None or ci >= entry["budget_ms" if has_ms else "budget_kb"], name


def test_main_strict_and_json(tmp_path, capsys):
    f = tmp_path / "perf.txt"
    f.write_text(RUN, encoding="utf-8")
    assert pbr.main([str(f)]) == 0
    assert pbr.main([str(f), "--strict"]) == 1
    capsys.readouterr()
    assert pbr.main([str(f), "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert any(r["nom"] == "sky_clouds_frame" and r["etat"] == "DÉPASSÉ" for r in rows)
