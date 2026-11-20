"""File des bancs en étapes courtes avec reprise (plan du 19 novembre) et garde-fou du cache de menu_bench."""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fb = _load("file_bancs", ROOT / "scripts" / "file_bancs.py")
mb = _load("menu_bench", ROOT / "engine" / "tests" / "menu_bench.py")

PY = sys.executable


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def depot(tmp_path):
    """Dépôt avec une origine : main et une branche, chacune avec un dossier Open_ride_linux."""
    origine = tmp_path / "origine"
    origine.mkdir()
    _git(origine, "init", "-q", "-b", "main")
    _git(origine, "config", "user.email", "t@t")
    _git(origine, "config", "user.name", "t")
    (origine / "Open_ride_linux").mkdir()
    (origine / "Open_ride_linux" / "x.txt").write_text("main", encoding="utf-8")
    _git(origine, "add", ".")
    _git(origine, "commit", "-q", "-m", "main")
    _git(origine, "checkout", "-q", "-b", "br")
    (origine / "Open_ride_linux" / "x.txt").write_text("branche", encoding="utf-8")
    _git(origine, "commit", "-q", "-am", "br")
    _git(origine, "checkout", "-q", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origine), str(clone)], check=True)
    return origine, clone


def _cmd(code, texte=""):
    """Commande d'étape : écrit un texte, compte ses passages dans {sortie}.n, rend un code."""
    script = (f"import pathlib,sys; p=pathlib.Path(sys.argv[1]+\".n\"); p.write_text(str(int(p.read_text() or 0)+1) "
              f"if p.exists() else '1'); print({texte!r}); sys.exit({code})")
    return f"{PY} -c {json.dumps(script)} {{sortie}}"


def _file(tmp_path, clone, prs: str) -> Path:
    f = tmp_path / "file.toml"
    f.write_text(f'[file]\ndepot = "{clone}"\nsortie = "{tmp_path / "sortie"}"\n{prs}', encoding="utf-8")
    return f


def _etat(tmp_path):
    return json.loads((tmp_path / "sortie" / "etat.json").read_text(encoding="utf-8"))


def _passages(tmp_path, pr, etape):
    p = tmp_path / "sortie" / pr / etape / "rapport.n"
    return int(p.read_text()) if p.exists() else 0


def test_classer_separe_contacts_environnement_et_echec():
    assert fb.classer(0, "")[0] == fb.OK
    assert fb.classer(1, "[ÉCHEC] décor : aucun contact sur la route : 3")[0] == fb.CONTACTS
    v, d = fb.classer(1, "[ÉCHEC] décor : aucun contact sur la route : 3\n[ÉCHEC] pire image : 140 ms")
    assert v == fb.ACOUPS and "1 à-coup(s) connu(s), 1 contact(s)" in d
    assert fb.classer(1, "[ÉCHEC] images lentes : 8 par minute")[0] == fb.ACOUPS
    assert fb.ACOUPS in fb.ACQUIS
    v, d = fb.classer(1, "[ÉCHEC] pire image : 140 ms\n[ÉCHEC] pont : tablier absent")
    assert v == fb.ECHEC and "2 échec(s)" in d
    assert fb.classer(1, "CompileError: x.sqlite : schéma 2 au lieu de 1, refaire `region-add`")[0] == fb.ENV
    assert fb.classer(2, "Godot introuvable : /x")[0] == fb.ENV
    assert fb.classer(1, "Traceback")[0] == fb.ECHEC


def test_fumees_dabord_puis_risque_et_pr_bloquee(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "sure"
branche = "br"
risque = 3
fumee = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}

[[pr]]
id = "risquee"
branche = "br"
risque = 1
fumee = {json.dumps(_cmd(1, "[ÉCHEC] départ du monde ouvert : refusé"))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
""")
    journal = []
    r = fb.Runner(fb.lire_file(f), reseau=False, log=journal.append)
    assert r.lancer() == 1
    lancees = [l.split()[1] for l in journal if l.startswith("→")]
    assert lancees == ["risquee/fumee", "sure/fumee", "sure/low"]   # fumées d'abord, risque 1 en tête
    etat = _etat(tmp_path)["prs"]
    assert etat["risquee"]["low"]["verdict"] == fb.BLOQUE
    assert etat["sure"]["low"]["verdict"] == fb.OK
    assert "BLOQUÉ" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_reprise_ne_rejoue_pas_les_etapes_ok(tmp_path, depot):
    _, clone = depot
    marque = tmp_path / "high_ok"
    high = (f"{PY} -c \"import pathlib,sys; sys.exit(0 if pathlib.Path(r'{marque}').exists() else 1)\"")
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "high"
commande = {json.dumps(high)}
""")
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    assert _etat(tmp_path)["prs"]["p"]["high"]["verdict"] == fb.ECHEC
    marque.touch()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 1          # low n'a pas été rejoué
    assert _etat(tmp_path)["prs"]["p"]["high"]["verdict"] == fb.OK


def test_relancer_apres_correction_garde_les_ok_de_lancienne_tete(tmp_path, depot):
    origine, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
fumee = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "low"
commande = {json.dumps(_cmd(0))}
[[pr.etape]]
id = "high"
commande = "{PY} -c \\"import pathlib,sys; sys.exit(0 if pathlib.Path('x.txt').read_text()=='corrigé' else 1)\\""
""")
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    # Correction poussée sur la branche : nouvelle tête.
    _git(origine, "checkout", "-q", "br")
    (origine / "Open_ride_linux" / "x.txt").write_text("corrigé", encoding="utf-8")
    _git(origine, "commit", "-q", "-am", "corrige")
    _git(clone, "fetch", "-q", "origin")
    assert fb.main(["relancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 1          # OK de l'ancienne tête gardé
    assert _passages(tmp_path, "p", "fumee") == 2        # fumée rejouée avant le rebanc ciblé
    etat = _etat(tmp_path)["prs"]["p"]
    assert etat["high"]["verdict"] == fb.OK and etat["low"]["tete"] != etat["high"]["tete"]
    assert "sur tête" in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")
    # `lancer` sur la nouvelle tête, lui, rejoue tout.
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert _passages(tmp_path, "p", "low") == 2


def test_reference_main_commune_a_toute_la_file(tmp_path, depot):
    _, clone = depot
    etape_main = f"""[[pr.etape]]
id = "main-low"
sur = "main"
commande = {json.dumps(_cmd(0))}
"""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "a"\nbranche = "br"\n{etape_main}\n[[pr]]\nid = "b"\nbranche = "br"\n{etape_main}')
    journal = []
    assert fb.Runner(fb.lire_file(f), reseau=False, log=journal.append).lancer() == 0
    assert sum(l.startswith("→") for l in journal) == 1     # main joué une seule fois pour les deux PR


def test_pause_et_delai(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f"""
[[pr]]
id = "p"
branche = "br"
[[pr.etape]]
id = "long"
commande = "{PY} -c 'import time; time.sleep(30)'"
delai_min = 0.02
""")
    (tmp_path / "sortie").mkdir()
    (tmp_path / "sortie" / "PAUSE").touch()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 3
    (tmp_path / "sortie" / "PAUSE").unlink()
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    assert _etat(tmp_path)["prs"]["p"]["long"]["verdict"] == fb.DELAI


def test_file_invalide(tmp_path, depot):
    _, clone = depot
    g = _file(tmp_path, clone, '[[pr]]\nid = "p"\nbranche = "br"\ncache = "partage"\n')
    assert fb.main(["etat", str(g)]) == 2


def test_cache_separe_amorce_et_variable(tmp_path, depot, monkeypatch):
    _, clone = depot
    home = tmp_path / "home"
    (home / "OpenRide" / "Cache" / "monde" / "brut").mkdir(parents=True)
    (home / "OpenRide" / "Cache" / "monde" / "brut" / "a.txt").write_text("reel", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    cmd = f"{PY} -c \"import os; print(os.environ['OPENRIDE_BANC_CACHES'])\""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "br"\ncache = "separe"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    racine = tmp_path / "sortie" / "caches" / "mer"
    assert (racine / "monde" / "brut" / "a.txt").read_text(encoding="utf-8") == "reel"
    assert str(racine) in (tmp_path / "sortie" / "mer" / "low" / "journal.txt").read_text(encoding="utf-8")


def _base(path: Path, schema: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE meta(key TEXT, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (schema,))
    con.commit()
    con.close()


def test_menu_bench_refuse_un_cache_reel_dun_autre_schema(tmp_path, monkeypatch):
    cache = tmp_path / "monde"
    _base(cache / "brut" / "osm" / "tuiles.sqlite", "2")
    msg = mb.schema_guard(cache, "1")
    assert msg and "schéma 2" in msg and fb.classer(1, f"[ÉCHEC] cache : {msg}")[0] == fb.ENV
    assert mb.schema_guard(cache, "2") is None
    assert mb.branch_schema_version() == "1"
    monkeypatch.setenv(mb.VARIABLE_CACHES_BANC, str(tmp_path / "pr907"))
    assert mb.open_world_cache_dir() == (tmp_path / "pr907" / "monde", False)
    monkeypatch.delenv(mb.VARIABLE_CACHES_BANC)
    assert mb.open_world_cache_dir()[1] is True


def _branche(origine, nom, fichiers, depuis="main"):
    _git(origine, "checkout", "-q", "-b", nom, depuis)
    for rel, texte in fichiers.items():
        p = origine / "Open_ride_linux" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte, encoding="utf-8")
    _git(origine, "add", ".")
    _git(origine, "commit", "-q", "-m", nom)
    _git(origine, "checkout", "-q", "main")


def test_portail_attend_puis_apres_etape_recoit_le_verdict(tmp_path, depot):
    _, clone = depot
    compteur, trace = tmp_path / "portail.n", tmp_path / "apres.txt"
    portail = (f"{PY} -c \"import pathlib,sys; p=pathlib.Path(r'{compteur}'); n=int(p.read_text()) if p.exists() else 0; "
               f"p.write_text(str(n+1)); print('Godot du user ouvert'); sys.exit(0 if n >= 2 else 1)\"")
    apres = f"{PY} -c \"import sys; open(r'{trace}','a').write(' '.join(sys.argv[1:])+chr(10))\" {{pr}} {{etape}} {{verdict}}"
    f = tmp_path / "file.toml"
    f.write_text(f'[file]\ndepot = "{clone}"\nsortie = "{tmp_path / "sortie"}"\nattente_s = 0\n'
                 f'avant_etape = {json.dumps(portail)}\napres_etape = {json.dumps(apres)}\n'
                 f'[[pr]]\nid = "p"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n',
                 encoding="utf-8")
    journal = []
    assert fb.Runner(fb.lire_file(f), reseau=False, log=journal.append).lancer() == 0
    assert int(compteur.read_text()) == 3                    # deux refus, puis feu vert
    assert any("en attente avant p/low : Godot du user ouvert" in l for l in journal)
    assert trace.read_text(encoding="utf-8").split() == ["p", "low", "OK"]
    assert _etat(tmp_path)["prs"]["p"]["low"]["apres_etape"] == "OK"


def test_essai_assemble_fusionne_les_branches(tmp_path, depot):
    origine, clone = depot
    _branche(origine, "b2", {"y.txt": "b2"})
    _git(clone, "fetch", "-q", "origin")
    cmd = f"{PY} -c \"import pathlib; print(pathlib.Path('x.txt').read_text(), pathlib.Path('y.txt').read_text())\""
    f = _file(tmp_path, clone, f'[[pr]]\nid = "essai-ow"\nbranche = "br"\nassemblage = ["b2"]\n'
                               f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    assert "branche b2" in (tmp_path / "sortie" / "essai-ow" / "low" / "journal.txt").read_text(encoding="utf-8")
    v = _etat(tmp_path)["prs"]["essai-ow"]["low"]
    assert v["verdict"] == fb.OK and "+" in v["tete"]
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0   # même assemblage : rien de rejoué
    assert "sur tête" not in (tmp_path / "sortie" / "etat.md").read_text(encoding="utf-8")


def test_pr_qui_change_le_schema_jamais_sur_le_cache_reel(tmp_path, depot):
    origine, clone = depot
    src = "compiler/src/openride_compiler/worldgen/osmdb.py"
    _branche(origine, "base", {src: "SCHEMA_VERSION = 1\n"})
    _git(origine, "checkout", "-q", "main")
    _git(origine, "merge", "-q", "base")
    _branche(origine, "mer", {src: "SCHEMA_VERSION = 2\n"})
    _git(clone, "fetch", "-q", "origin")
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "mer"\n{etape}')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    v = _etat(tmp_path)["prs"]["mer"]["low"]
    assert v["verdict"] == fb.ENV and "1 → 2" in v["detail"]
    assert _passages(tmp_path, "mer", "low") == 0             # rien lancé
    g = _file(tmp_path, clone, f'[[pr]]\nid = "mer"\nbranche = "mer"\ncache = "separe"\n{etape}')
    assert fb.main(["lancer", str(g), "--sans-reseau"]) == 0


def test_tete_changee_en_cours_de_file_ne_bloque_que_sa_pr(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, f'[[pr]]\nid = "vieille"\nbranche = "br"\ntete = "deadbeef"\n'
                               f'fumee = {json.dumps(_cmd(0))}\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n'
                               f'[[pr]]\nid = "ok"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 1
    etat = _etat(tmp_path)["prs"]
    assert etat["vieille"]["fumee"]["verdict"] == fb.ENV and "deadbeef" in etat["vieille"]["fumee"]["detail"]
    assert etat["vieille"]["low"]["verdict"] == fb.BLOQUE and etat["ok"]["low"]["verdict"] == fb.OK


def test_portail_pc_fenetre_du_user_et_godot(tmp_path):
    """portail_pc.sh : attend la fin de la fenêtre du user (ou son marqueur) et l'absence de Godot."""
    import time

    script = ROOT / "scripts" / "file_bancs" / "portail_pc.sh"
    binf = tmp_path / "bin"
    binf.mkdir()
    pgrep = binf / "pgrep"
    pgrep.write_text("#!/bin/sh\n[ -f \"$GODOT_OUVERT\" ] && { echo '42 Godot_v4.7'; exit 0; }\nexit 1\n", encoding="utf-8")
    pgrep.chmod(0o755)
    fen = tmp_path / "fenetre.txt"
    now = int(time.time())
    fen.write_text(f"{now + 600} {now + 3600} pc_rendu\n", encoding="utf-8")
    env = {"PATH": f"{binf}:/usr/bin:/bin", "HOME": str(tmp_path), "FENETRE": str(fen),
           "GODOT_OUVERT": str(tmp_path / "godot"), "FILE_DUREE_MIN": "30"}

    def code(**extra):
        return subprocess.run(["bash", str(script)], env={**env, **extra}, capture_output=True, text=True)

    p = code()
    assert p.returncode == 1 and "fenêtre du user" in p.stdout     # 30 min déborderaient sur la fenêtre
    assert code(FILE_DUREE_MIN="5").returncode == 0                  # 5 min finissent avant
    (tmp_path / "pc_rendu").touch()
    assert code().returncode == 0                                    # marqueur « PC rendu »
    (tmp_path / "godot").touch()
    p = code()
    assert p.returncode == 1 and "Godot" in p.stdout


def test_exemple_rfs3_se_lit():
    f = fb.lire_file(ROOT / "scripts" / "file_bancs" / "exemple_rFS3.toml")
    assert [e.id for e in f.prs[0].etapes] == ["fumee", "tests-engine", "low", "high", "medium"]
    assert f.avant_etape and f.apres_etape and "{dossier}" in f.apres_etape


def test_depot_qui_ne_suit_que_main(tmp_path, depot):
    """Dépôt du user : refspec de fetch réduite à main ; la file doit quand même trouver la tête de la branche."""
    _, clone = depot
    _git(clone, "config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    _git(clone, "update-ref", "-d", "refs/remotes/origin/br")
    f = _file(tmp_path, clone, f'[[pr]]\nid = "p"\nbranche = "br"\n[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    assert fb.Runner(fb.lire_file(f), reseau=True, log=lambda *_: None).lancer() == 0
    assert _etat(tmp_path)["prs"]["p"]["low"]["verdict"] == fb.OK


def test_environnement_des_etapes_comme_job_sh(tmp_path, depot):
    """PYTHONPATH sur les sources du worktree et core/.venv du dépôt (étape tests-engine de rFS3 du 19 novembre)."""
    origine, clone = depot
    _branche(origine, "eng", {"core/a.txt": "x"})
    _git(clone, "fetch", "-q", "origin")
    venv = clone / "Open_ride_linux" / "core" / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("", encoding="utf-8")
    cmd = (f"{PY} -c \"import os; print(os.environ['PYTHONPATH']); print(os.environ['VIRTUAL_ENV']); "
           f"print(os.environ['PATH'].split(os.pathsep)[0]); print(os.environ['LC_NUMERIC'])\"")
    f = _file(tmp_path, clone, f'[[pr]]\nid = "p"\nbranche = "eng"\n[[pr.etape]]\nid = "tests-engine"\ncommande = {json.dumps(cmd)}\n')
    assert fb.main(["lancer", str(f), "--sans-reseau"]) == 0
    projet = tmp_path / "sortie" / "worktrees" / "p" / "Open_ride_linux"
    lignes = (tmp_path / "sortie" / "p" / "tests-engine" / "journal.txt").read_text(encoding="utf-8").splitlines()
    assert lignes[0].split(os.pathsep)[:2] == [str(projet / "core" / "src"), str(projet / "compiler" / "src")]
    assert lignes[1] == str(venv.parent) and lignes[2] == str(venv) and lignes[3] == "C"
    assert (projet / "core" / ".venv").resolve() == venv.parent.resolve()


def test_assemblage_en_conflit_resolu_par_strategie(tmp_path, depot):
    origine, clone = depot
    _branche(origine, "b2", {"x.txt": "b2"})                 # même fichier que br : conflit
    _git(clone, "fetch", "-q", "origin")
    cmd = f"{PY} -c \"import pathlib; print(pathlib.Path('x.txt').read_text())\""
    etape = f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(cmd)}\n'
    f = _file(tmp_path, clone, f'[[pr]]\nid = "ow"\nbranche = "br"\nassemblage = ["b2"]\n{etape}')
    fb.main(["lancer", str(f), "--sans-reseau"])
    assert _etat(tmp_path)["prs"]["ow"]["low"]["verdict"] != fb.OK
    f = _file(tmp_path, clone, f'[[pr]]\nid = "ow"\nbranche = "br"\nassemblage = ["b2"]\n'
                               f'assemblage_strategie = "ours"\n{etape}')
    assert fb.main(["relancer", str(f), "--sans-reseau"]) == 0
    assert _etat(tmp_path)["prs"]["ow"]["low"]["verdict"] == fb.OK
    assert "branche" in (tmp_path / "sortie" / "ow" / "low" / "journal.txt").read_text(encoding="utf-8")


def test_strategie_inconnue_refusee(tmp_path, depot):
    _, clone = depot
    f = _file(tmp_path, clone, '[[pr]]\nid = "p"\nbranche = "br"\nassemblage_strategie = "octopus"\n'
                               f'[[pr.etape]]\nid = "low"\ncommande = {json.dumps(_cmd(0))}\n')
    with pytest.raises(fb.FileInvalide):
        fb.lire_file(f)
