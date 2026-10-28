"""Tableau de la recette 1.0 (lot X30) : O8 lu, rapports fabriqués dans un HOME temporaire."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tableau_recette.py"
spec = importlib.util.spec_from_file_location("tableau_recette", SCRIPT)
tr = importlib.util.module_from_spec(spec)
sys.modules["tableau_recette"] = tr
spec.loader.exec_module(tr)


def _run(home, tool, stamp, files):
    d = home / "OpenRide" / tool / stamp
    d.mkdir(parents=True)
    for name, content in files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return d


def _verdict(ok, text="fini"):
    return json.dumps({"type": "etape", "texte": "x"}) + "\n" + json.dumps({"type": "verdict", "ok": ok, "texte": text}) + "\n"


def test_o8_has_25_lines():
    lines = tr.read_o8()
    assert [ln["numero"] for ln in lines] == list(range(1, 26))
    assert lines[0]["bloquante"] and not lines[6]["bloquante"]          # ligne 7 (ceinture) non bloquante
    assert lines[5]["critere"].startswith("Click : boîtier gauche") and "Outil" not in lines[5]["critere"]
    assert lines[24]["groupe"] == "Documentation"
    assert set(tr.OUTILS) <= set(range(1, 26))


def test_empty_home(tmp_path):
    rows = {ln.numero: ln for ln in tr.build(tmp_path)}
    assert rows[3].resultat == "à la main" and rows[3].detail == "aucun outil"          # ligne sans outil
    assert rows[21].resultat == "à la main" and "fit-check" in rows[21].outil            # outil qui n'écrit rien
    assert rows[6].resultat == "à faire" and rows[6].detail == "aucun rapport"


def test_reports_are_found(tmp_path):
    _run(tmp_path, "click_recette", "2026-10-27_101500", {"guide.jsonl": _verdict(False), "rapport.txt": "x"})
    last = _run(tmp_path, "click_recette", "2026-10-28_093000",
                {"guide.jsonl": _verdict(True, "Recette finie : tout passe"), "rapport.txt": "x"})
    _run(tmp_path, "boutons_click", "2026-10-28_080000", {"rapport.json": {"ok": False}})
    _run(tmp_path, "recettes", "2026-10-28_070000",
         {"resume.json": {"ok": False, "steps": [{"name": "engine", "ok": True, "detail": "96 fichiers"},
                                                 {"name": "core", "ok": False}]}, "resume.txt": "x"})
    _run(tmp_path, "sim_bench", "2026-10-28_060000", {"guide.jsonl": _verdict(True), "index.html": "x", "demo/x": "1"})
    _run(tmp_path, "sim_bench", "2026-10-28_120000", {"guide.jsonl": _verdict(False), "index.html": "x"})
    _run(tmp_path, "sim_bench", "2026-10-27_120000", {"guide.jsonl": _verdict(True), "index.html": "x", "endurance/x": "1"})
    _run(tmp_path, "menu_bench", "2026-10-28_110000", {"resultats.json": [{"echecs": 0}, {"echecs": 0}], "rapport.html": "x"})
    _run(tmp_path, "recettes_install", "2026-10-28_050000",
         {"resume_docker.txt": "Recette\ninstallation neuve OK\n", "install.log": "x"})
    rows = {ln.numero: ln for ln in tr.build(tmp_path)}
    assert rows[6].resultat == "OK" and rows[6].date == "28/10/2026 09:30"          # le dernier rapport
    assert rows[6].rapport == str(last / "rapport.txt") and rows[6].detail == "Recette finie : tout passe"
    assert rows[5].resultat == "ÉCHEC"
    assert rows[19].resultat == "OK" and rows[19].detail.startswith("étape engine")  # étape de la recette du PC
    assert rows[17].resultat == "ÉCHEC" and rows[17].date == "28/10/2026 12:00"
    assert rows[18].resultat == "OK" and rows[18].date == "27/10/2026 12:00"         # scénario endurance seul
    assert rows[20].resultat == "OK" and rows[20].rapport.endswith("rapport.html")
    assert rows[1].resultat == "OK" and rows[1].rapport.endswith("resume_docker.txt")
    assert rows[2].resultat == "à faire"                                              # pas de passage « home »


def test_html_and_json(tmp_path, capsys):
    _run(tmp_path, "click_recette", "2026-10-28_093000", {"guide.jsonl": _verdict(True)})
    assert tr.main(["--home", str(tmp_path)]) == 0
    page = (tmp_path / "OpenRide" / "recette_1_0" / "tableau.html").read_text(encoding="utf-8")
    assert page.count("<tr data-n=") == 25 and "localStorage" in page and "Exporter en JSON" in page
    assert "1 ligne(s) OK sur 25" in page and "file://" in page
    assert "Recette 1.0 : 25 lignes ; 1 OK" in capsys.readouterr().out
    assert tr.main(["--home", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 25 and data[5]["resultat"] == "OK"
