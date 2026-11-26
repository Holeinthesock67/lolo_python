"""Contrôle avant poussée (scripts/avant_poussee.py, lot AP1, 26 novembre)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("avant_poussee", ROOT / "scripts" / "avant_poussee.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["avant_poussee"] = mod
    spec.loader.exec_module(mod)
    return mod


ap = _load()


def test_uid_manquant_vu_puis_ecrit(tmp_path):
    engine = tmp_path / "engine"
    (engine / "tests" / "unit").mkdir(parents=True)
    (engine / "a.gd").write_text("extends Node\n")
    (engine / "a.gd.uid").write_text("uid://abc123\n")
    (engine / "tests" / "unit" / "test_b.gd").write_text("extends Node\n")
    (engine / ".godot").mkdir()
    (engine / ".godot" / "cache.gd").write_text("")                        # dossier de Godot : ignoré
    b = ap.Bilan()
    ap.controle_uid(engine, corriger=False, bilan=b)
    assert b.echecs == 1 and "tests/unit/test_b.gd" in b.lignes[-1][1]
    b = ap.Bilan()
    ap.controle_uid(engine, corriger=True, bilan=b)
    assert b.echecs == 0
    uid = (engine / "tests" / "unit" / "test_b.gd.uid").read_text().strip()
    assert ap.UID_RE.fullmatch(uid) and uid != "uid://abc123"
    b = ap.Bilan()
    ap.controle_uid(engine, corriger=False, bilan=b)
    assert b.lignes == [(ap.OK, ".uid : les 2 scripts GDScript ont le leur")]


def test_uid_en_double_ou_mal_forme(tmp_path):
    engine = tmp_path / "engine"
    engine.mkdir()
    for nom in ("a", "b"):
        (engine / f"{nom}.gd").write_text("")
        (engine / f"{nom}.gd.uid").write_text("uid://meme\n")
    (engine / "c.gd").write_text("")
    (engine / "c.gd.uid").write_text("pas un uid\n")
    b = ap.Bilan()
    ap.controle_uid(engine, corriger=False, bilan=b)
    textes = " ".join(t for _, t in b.lignes)
    assert b.echecs == 2 and "en double" in textes and "mal formé" in textes


def test_nouvel_uid_format_godot_et_unique():
    pris: set[str] = set()
    for _ in range(200):
        u = ap.nouvel_uid(pris)
        assert ap.UID_RE.fullmatch(u) and u not in pris
        pris.add(u)


def test_versions_comparees_a_main_actuelle(tmp_path, monkeypatch):
    """Révision IPC montée par la branche, mais déjà prise sur main par une autre PR : échec, numéro proposé."""
    valeurs = {("base", "révision IPC"): "1.35", ("HEAD", "révision IPC"): "1.36", ("main", "révision IPC"): "1.36"}
    monkeypatch.setattr(ap, "version", lambda rev, nom: valeurs.get((rev, nom), "9"))
    b = ap.Bilan()
    ap.controle_versions("base", "main", b)
    assert b.echecs == 1 and "renuméroter en 1.37" in b.lignes[0][1]
    valeurs[("main", "révision IPC")] = "1.35"
    b = ap.Bilan()
    ap.controle_versions("base", "main", b)
    assert b.echecs == 0 and b.lignes[0][0] == ap.OK
    assert ap.cle_version("1.10") > ap.cle_version("1.9") and ap.suivante("1.9") == "1.10"


def test_tests_touches_par_la_branche():
    changes = ["core/tests/test_controle_sol_route.py", "core/src/openride_core/tools/power_curve.py",
               "compiler/src/openride_compiler/worldgen/__init__.py", "docs/lots/LOT_X.md",
               "core/tests/test_absent_supprime.py"]
    t = ap.tests_touches(changes)
    assert "tests/test_controle_sol_route.py" in t["core"]
    assert "tests/test_power_curve.py" in t["core"]
    assert "tests/test_absent_supprime.py" not in t["core"]
    assert t["compiler"] == set()


def test_sur_le_depot_sans_reseau_ni_tests():
    """Le script tourne sur le dépôt lui-même (main ou branche) et rend 0 ou 1, jamais une erreur d'appel."""
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "avant_poussee.py"), "--sans-reseau", "--sans-tests",
                        "--main", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert p.returncode in (0, 1), p.stdout + p.stderr
    assert "[OK] assemblage avec main : sans conflit" in p.stdout
