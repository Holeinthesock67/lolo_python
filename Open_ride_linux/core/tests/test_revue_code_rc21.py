"""Lot RC21 : constats de confort de la revue de code vague 5 (outils, tests, scripts), hors file des bancs,
pré-vol, confidentialité, sondes de performance et installation (statut/REVUE_CODE_5_OUTILS.md)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]      # Open_ride_linux/
ENGINE_TESTS = ROOT / "engine" / "tests"
SCRIPTS = ROOT / "scripts"


def charger(chemin: Path, nom: str):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nom] = mod
    spec.loader.exec_module(mod)
    return mod


# --- O2-18 : portail_pc.sh refuse une fenêtre mal formée ----------------------------------------------

@pytest.mark.parametrize("contenu", ["", "\n", "1700000000\n", "abc def pc_rendu\n", "1700000000 1,5 pc_rendu\n"])
def test_portail_pc_refuse_une_fenetre_mal_formee(tmp_path, contenu):
    script = SCRIPTS / "file_bancs" / "portail_pc.sh"
    binf = tmp_path / "bin"
    binf.mkdir()
    (binf / "pgrep").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")     # aucun Godot
    (binf / "pgrep").chmod(0o755)
    fen = tmp_path / "fenetre.txt"
    fen.write_text(contenu, encoding="utf-8")
    env = {"PATH": f"{binf}:/usr/bin:/bin", "HOME": str(tmp_path), "FENETRE": str(fen), "FILE_DUREE_MIN": "5"}
    p = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)
    assert p.returncode == 1 and "illisible" in p.stdout, p.stdout + p.stderr
    # Bien formée et loin dans le passé : le passage s'ouvre.
    now = int(time.time())
    fen.write_text(f"{now - 7200} {now - 3600} pc_rendu\n", encoding="utf-8")
    assert subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True).returncode == 0


# --- O3-05, O3-08, O3-09 : processus des bancs de l'engine ---------------------------------------------

def _bp():
    return charger(ENGINE_TESTS / "bancs_processus.py", "bancs_processus")


def test_arret_des_descendants_comme_xvfb_run():
    """O3-05 : `xvfb-run` (sh) ne transmet pas SIGTERM à son enfant ; les descendants sont arrêtés d'abord."""
    bp = _bp()
    p = subprocess.Popen(["sh", "-c", 'trap "echo fin" EXIT; sleep 60; :'])
    try:
        fin = time.monotonic() + 5
        while not bp.descendants(p.pid) and time.monotonic() < fin:
            time.sleep(0.05)
        enfants = bp.descendants(p.pid)
        assert enfants, "sleep non lancé"
        vises = bp.arreter_descendants(p.pid, delai_s=3.0)
        assert set(enfants) <= set(vises)
        assert not any(bp._vivant(e) for e in enfants)
        p.wait(timeout=5)           # le sh finit de lui-même une fois son enfant arrêté
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_sigterm_passe_par_les_finally(tmp_path):
    """O3-08 : SIGTERM ou SIGHUP lèvent une exception : le nettoyage des `finally` a lieu, code 128 + signal."""
    trace = tmp_path / "nettoye.txt"
    code = (f"import sys, time; sys.path.insert(0, {str(ENGINE_TESTS)!r})\n"
            "import bancs_processus\n"
            "bancs_processus.signaux_en_exception()\n"
            "try:\n    print('pret', flush=True)\n    time.sleep(30)\n"
            f"finally:\n    open({str(trace)!r}, 'w').write('ok')\n")
    import signal
    for sig, attendu in ((signal.SIGTERM, 143), (signal.SIGHUP, 129)):
        trace.unlink(missing_ok=True)
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "pret"
        p.send_signal(sig)
        assert p.wait(timeout=10) == attendu
        assert trace.read_text() == "ok"


def test_home_temporaire_pour_godot():
    """O3-09 : HOME et XDG du Godot des bancs dans un dossier neuf, hors du vrai profil."""
    bp = _bp()
    home, env = bp.home_temporaire()
    try:
        assert home.is_dir() and not any(home.iterdir())
        assert env["HOME"] == str(home) and env["XDG_DATA_HOME"] == str(home / ".local/share")
        assert set(env) == {"HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"}
    finally:
        import shutil
        shutil.rmtree(home, ignore_errors=True)


@pytest.mark.parametrize("banc", ["visual_check.py", "tour_visuel.py", "rogue_bench.py"])
def test_bancs_avec_home_temporaire_et_signaux(banc):
    """O3-08 et O3-09 : les trois bancs lancent Godot avec un HOME temporaire et gèrent SIGTERM / SIGHUP."""
    texte = (ENGINE_TESTS / banc).read_text(encoding="utf-8")
    assert "home_temporaire()" in texte and "**home_env" in texte
    assert "signaux_en_exception()" in texte
    assert "shutil.rmtree(home_godot" in texte


def test_sim_bench_arrete_godot_sous_xvfb_et_gere_les_signaux():
    texte = (ENGINE_TESTS / "sim_bench.py").read_text(encoding="utf-8")
    assert "bancs_processus.arreter_descendants(p.p.pid)" in texte
    assert "bancs_processus.signaux_en_exception()" in texte


# --- O3-06, O3-07 : run_engine_tests.sh ---------------------------------------------------------------

def test_run_engine_tests_arrete_ses_processus_et_borne_godot():
    texte = (ENGINE_TESTS / "run_engine_tests.sh").read_text(encoding="utf-8")
    assert "trap arreter_fond EXIT" in texte and "INT" in texte and "TERM" in texte
    assert texte.count('BG_PIDS+=(') == 4
    for script in ("test_world_streamer.gd", "test_erg_view_model.gd", "test_menu_ipc.gd"):
        ligne = next(ln for ln in texte.splitlines() if script in ln and '"$GODOT"' in ln)
        assert "timeout -k 5" in ligne, ligne
    assert "Rendu par tronçons : " in texte      # ligne de compte exigée
    assert subprocess.run(["bash", "-n", str(ENGINE_TESTS / "run_engine_tests.sh")]).returncode == 0


# --- O3-10 : référence jamais écrite depuis une scène en échec ----------------------------------------

def test_reference_non_ecrite_si_un_controle_a_echoue(tmp_path):
    vc = charger(ENGINE_TESTS / "visual_check.py", "visual_check")
    report = vc.Report()
    s = vc.Session("1280x720:low", 64, 48, None, tmp_path, report, tmp_path / "ref", {"*"})
    scene = next(iter(vc.GOLDEN_SCENES))
    img = vc.Image(64, 48, bytearray(64 * 48 * 3))
    cap = vc.Capture(s.name, scene, tmp_path / "x.png", {})
    s.check(scene, "tuiles du terrain toutes affichées", False, "3 tuile(s) encore en attente")
    s._golden(cap, img)
    assert not (tmp_path / "ref" / f"{scene}.png").exists()
    assert any(c.name == "image de référence écrite" and not c.ok for c in report.checks)
    autre = vc.Session("1280x720:medium", 64, 48, None, tmp_path, report, tmp_path / "ref2", {"*"})
    autre._golden(vc.Capture(autre.name, scene, tmp_path / "y.png", {}), img)
    assert (tmp_path / "ref2" / f"{scene}.png").exists()       # scène sans échec : référence écrite
